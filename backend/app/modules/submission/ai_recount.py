"""저장된 관절 좌표를 AI 내부 API에 보내 운동 기록을 재계산한다."""

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from pydantic.alias_generators import to_camel

from app.core.errors import AppError
from app.modules.submission.schemas import PoseCaptureIn, RepIn
from app.modules.workout_session.catalog import CATALOG_VERSION, CHUNK_MAX_BYTES
from app.modules.workout_session.models import PoseChunk, WorkoutSession
from app.modules.workout_session.service import LIVENESS_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)
_json = TypeAdapter(dict)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class _ResultModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, strict=True)


class _Rep(_ResultModel):
    index: int = Field(ge=1)
    end_t: int = Field(ge=0)
    accepted: bool


class _Liveness(_ResultModel):
    status: Literal["PASSED", "EXPIRED", "FAILED_NO_PERSON"]


class _Result(_ResultModel):
    recognized_reps: int = Field(ge=0)
    ai_confidence: float = Field(ge=0, le=1)
    reps: list[_Rep]
    liveness: _Liveness

    @model_validator(mode="after")
    def check_reps(self) -> "_Result":
        if self.recognized_reps != sum(rep.accepted for rep in self.reps):
            raise ValueError("인정 렙 수가 렙 목록과 일치하지 않습니다.")
        if len({rep.index for rep in self.reps}) != len(self.reps):
            raise ValueError("중복 렙 번호가 있습니다.")
        return self


class _Response(_ResultModel):
    result: _Result


@dataclass(frozen=True)
class WorkoutRecount:
    counted_reps: int
    confidence: float
    reps: Sequence[RepIn]
    liveness_passed: bool | None


def _epoch_ms(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def _engine_chunks(session_id: str, chunks: Sequence[PoseChunk], origin: int) -> list[dict]:
    """배열을 관절 객체로 바꾸면서 커진 청크는 내부 API 제한에 맞춰 나눈다."""
    result: list[dict] = []
    for stored in chunks:
        chunk = {"sessionId": session_id, "seq": len(result), "frames": []}
        size = len(_json.dump_json(chunk))
        for raw in stored.frames:
            frame = {
                "t": raw["t"] - origin,
                "landmarks": [
                    None if kp is None else {"x": kp[0], "y": kp[1], "z": None, "visibility": kp[2]}
                    for kp in raw["kp"]
                ],
            }
            frame_size = len(_json.dump_json(frame))
            separator = 1 if chunk["frames"] else 0
            if size + frame_size + separator > CHUNK_MAX_BYTES:
                result.append(chunk)
                chunk = {"sessionId": session_id, "seq": len(result), "frames": []}
                size = len(_json.dump_json(chunk))
                separator = 0
            size += frame_size + separator
            chunk["frames"].append(frame)
        result.append(chunk)
    return result


def _post_recount(payload: dict) -> _Result:
    token = os.environ.get("AI_INTERNAL_TOKEN")
    if not token:
        logger.error("AI_INTERNAL_TOKEN is missing")
        raise AppError(503, "AI_UNAVAILABLE", "운동 판정 서비스에 연결할 수 없습니다.")

    url = os.environ.get("AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
    try:
        response = httpx.post(
            f"{url}/internal/recount",
            json=payload,
            headers={"X-Internal-Token": token},
            timeout=5.0,
            trust_env=False,
        )
        if response.status_code == 400 and response.json().get("code") == "VALIDATION_FAILED":
            raise AppError(
                400, "VALIDATION_FAILED", "관절 좌표나 촬영 정보가 올바르지 않습니다.",
                {"reason": "INVALID_POSE_DATA"},
            )
        response.raise_for_status()
        return _Response.model_validate_json(response.content).result
    except (httpx.HTTPError, httpx.InvalidURL, ValidationError, ValueError, AttributeError) as exc:
        logger.warning("AI recount request failed (%s)", type(exc).__name__)
        raise AppError(503, "AI_UNAVAILABLE", "운동 판정 서비스에 연결할 수 없습니다.") from exc


def recount_workout(
    session: WorkoutSession,
    chunks: Sequence[PoseChunk],
    capture: PoseCaptureIn,
    *,
    client_rep_count: int,
    reps: Sequence[RepIn],
    ai_confidence: float,
) -> WorkoutRecount:
    session_id = str(session.id)
    issued_at = _epoch_ms(session.liveness_issued_at)
    origin = min(issued_at, chunks[0].frames[0]["t"])
    client_reps = []
    for rep in reps:
        # API-026은 완료 시각만 받으므로 렙 구간 교집합을 비교할 수 없다.
        end = _epoch_ms(rep.ts) - origin
        if end >= 0:
            client_reps.append({"startT": end, "endT": end, "accepted": rep.counted})
    payload = {
        "meta": {
            "sessionId": session_id,
            "exerciseType": session.exercise_code,
            "catalogVersion": CATALOG_VERSION,
            "fps": capture.fps,
            "imageWidth": capture.image_width,
            "imageHeight": capture.image_height,
            "mirrored": capture.mirrored,
            "device": {"platform": capture.platform, "modelVersion": capture.model_version},
            "liveness": {
                "challengeId": str(session.liveness_challenge_id),
                "action": session.liveness_action,
                "issuedAtT": issued_at - origin,
                "expiresAtT": issued_at - origin + LIVENESS_TIMEOUT_SECONDS * 1000,
            },
        },
        "chunks": _engine_chunks(session_id, chunks, origin),
        "client": {"clientRepCount": client_rep_count, "reps": client_reps, "aiConfidence": ai_confidence},
    }
    result = _post_recount(payload)
    first_t = chunks[0].frames[0]["t"] - origin
    last_t = chunks[-1].frames[-1]["t"] - origin
    if any(not first_t <= rep.end_t <= last_t for rep in result.reps):
        raise AppError(503, "AI_UNAVAILABLE", "운동 판정 서비스 응답이 올바르지 않습니다.")
    try:
        events = [
            RepIn(
                rep_no=rep.index,
                ts=_EPOCH + timedelta(milliseconds=origin + rep.end_t),
                counted=rep.accepted,
            )
            for rep in result.reps
        ]
    except OverflowError as exc:
        raise AppError(503, "AI_UNAVAILABLE", "운동 판정 서비스 응답이 올바르지 않습니다.") from exc
    return WorkoutRecount(
        result.recognized_reps, result.ai_confidence, events, result.liveness.status == "PASSED"
    )
