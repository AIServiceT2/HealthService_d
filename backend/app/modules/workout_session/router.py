"""session API. 노션 '전운시 API 명세서' API-018~027.

구현한 것: API-018~025. API-027(세션 폐기)은 아직 501.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token).
"""

import uuid

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError

from app.core.stub import not_implemented
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workout_session import service
from app.modules.workout_session.catalog import (
    CATALOG_VERSION,
    CHUNK_MAX_BYTES,
    CHUNK_MAX_FRAMES,
    EXERCISES,
)
from app.modules.workout_session.schemas import (
    ChunkSpecOut,
    DailyCapItem,
    DailyCapsResponse,
    ExerciseCriteria,
    ExerciseItem,
    ExercisesResponse,
    LivenessChallengeOut,
    LivenessRequest,
    LivenessResponse,
    PauseRequest,
    PoseChunkRequest,
    PoseChunkResponse,
    SessionStatusResponse,
    StartSessionRequest,
    StartSessionResponse,
)

router = APIRouter(tags=["session"])


async def _body_bytes(request: Request) -> int:
    """요청 본문의 실제 바이트 수 (청크 크기 제한 검사용, 노션 API-022)."""
    return len(await request.body())


@router.get(
    "/exercises",
    summary="[API-018] 운동 목록·판정 기준·튜토리얼",
    description="권한: PLAYER. MVP 운동은 스쿼트 1종. 가동범위 수치·권장 촬영 각도·튜토리얼은 미정이라 null",
    response_model=ExercisesResponse,
)
def api_018(_: User = Depends(get_current_user)) -> ExercisesResponse:
    return ExercisesResponse(
        catalog_version=CATALOG_VERSION,
        items=[
            ExerciseItem(
                code=e.code, name=e.name, daily_cap=e.daily_cap, criteria=ExerciseCriteria()
            )
            for e in EXERCISES.values()
        ],
    )


@router.get(
    "/me/daily-caps",
    summary="[API-019] 내 일일 상한 조회",
    description=(
        "권한: PLAYER. date는 KST. 임시: reserved는 제출(API-026)이 아직 없어 항상 0"
    ),
    response_model=DailyCapsResponse,
)
def api_019(user: User = Depends(get_current_user)) -> DailyCapsResponse:
    day = service.today_kst()
    return DailyCapsResponse(
        date=day,
        items=[
            DailyCapItem(
                exercise_code=c.exercise.code,
                cap=c.exercise.daily_cap,
                reserved=c.reserved,
                remaining=c.remaining,
            )
            for c in service.daily_caps(user.id, day)
        ],
    )


@router.post(
    "/workout-sessions",
    summary="[API-020] 운동 세션 시작",
    description=(
        "권한: PLAYER. 무작위 동작 지시(liveness)를 함께 내려준다. "
        "없는 운동 코드는 400 VALIDATION_FAILED. 일일 상한이 다 차도 막지 않음(차단 여부 미정)"
    ),
    status_code=201,
    response_model=StartSessionResponse,
)
def api_020(
    req: StartSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StartSessionResponse:
    goal = service.Goal(req.goal.reps, req.goal.sets) if req.goal else None
    target = service.Target(req.target.type, req.target.id) if req.target else None
    session, cap = service.start_session(db, user.id, req.exercise_code, goal, target)
    return StartSessionResponse(
        session_id=session.id,
        status=session.status,
        catalog_version=CATALOG_VERSION,
        remaining_daily_cap=cap.remaining,
        liveness=LivenessChallengeOut(
            challenge_id=session.liveness_challenge_id,
            action=session.liveness_action,
            timeout_sec=service.LIVENESS_TIMEOUT_SECONDS,
        ),
        chunk_spec=ChunkSpecOut(max_frames=CHUNK_MAX_FRAMES, max_bytes=CHUNK_MAX_BYTES),
    )


@router.post(
    "/workout-sessions/{id}/liveness",
    summary="[API-021] 무작위 동작 확인 결과 전송",
    description=(
        "권한: OWNER. 발급한 동작과 같고 제한 시간(서버 시각 기준) 안이면 통과. "
        "실패는 422 LIVENESS_FAILED, 이미 확인했거나 진행 중이 아니면 409 INVALID_STATE. "
        "재시도는 허용하지 않음(실패 정책 미정)"
    ),
    response_model=LivenessResponse,
)
def api_021(
    id: uuid.UUID,
    req: LivenessRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LivenessResponse:
    passed = service.submit_liveness(db, user.id, id, req.challenge_id, req.detected_action)
    if not passed:
        raise AppError(
            422, "LIVENESS_FAILED", "지시한 동작을 확인하지 못했습니다.", {"retryAllowed": False}
        )
    return LivenessResponse(passed=True, retry_allowed=False)


@router.put(
    "/workout-sessions/{id}/pose-chunks/{seq}",
    summary="[API-022] 관절 좌표 청크 업로드",
    description=(
        "권한: OWNER. kp는 [x, y, visibility] 배열이고 얼굴 랜드마크 자리는 null. "
        "관절 33개(MediaPipe)면 0~10번, 17개(MoveNet)면 0~4번이 얼굴. "
        "청크 300프레임·256KB 초과, 얼굴 좌표 포함, 경로와 본문 seq가 다르면 400 VALIDATION_FAILED. "
        "같은 seq는 덮어씀. 종료된 세션이면 409 INVALID_STATE"
    ),
    response_model=PoseChunkResponse,
)
def api_022(
    req: PoseChunkRequest,
    id: uuid.UUID,
    seq: int = Path(ge=1),
    body_bytes: int = Depends(_body_bytes),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PoseChunkResponse:
    if req.seq != seq:
        raise AppError(
            400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": "SEQ_MISMATCH"}
        )
    frames = [f.model_dump() for f in req.frames]
    received = service.upload_chunk(db, user.id, id, seq, frames, body_bytes)
    return PoseChunkResponse(received=received)


@router.post(
    "/workout-sessions/{id}/pause",
    summary="[API-023] 세션 일시중지",
    description="권한: OWNER. ACTIVE → PAUSED. 진행 중이 아니면 409 INVALID_STATE",
    response_model=SessionStatusResponse,
)
def api_023(
    id: uuid.UUID,
    req: PauseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionStatusResponse:
    session = service.pause_session(db, user.id, id)
    return SessionStatusResponse(session_id=session.id, status=session.status)


@router.post(
    "/workout-sessions/{id}/resume",
    summary="[API-024] 세션 재개",
    description="권한: OWNER",
    status_code=501,
)
def api_024(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/workout-sessions/{id}",
    summary="[API-025] 세션 상태 조회",
    description="권한: OWNER",
    status_code=501,
)
def api_025(id: uuid.UUID) -> None:
    not_implemented()


@router.delete(
    "/workout-sessions/{id}",
    summary="[API-027] 세션 폐기",
    description="권한: OWNER",
    status_code=501,
)
def api_027(id: uuid.UUID) -> None:
    not_implemented()
