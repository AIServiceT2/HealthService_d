"""모든 입출력 pydantic 모델.

JSON 필드는 camelCase, Python 속성은 snake_case다 (`alias_generator=to_camel`).
직렬화는 항상 alias(camelCase)로 한다: `model.to_json()` / `model.to_dict()`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """camelCase 별칭을 쓰는 공통 기반 모델. 정의되지 않은 필드는 거부한다."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    def to_dict(self) -> dict[str, Any]:
        """camelCase JSON 호환 dict."""
        return self.model_dump(mode="json", by_alias=True)

    def to_json(self) -> str:
        """camelCase JSON 문자열 (필드 순서 고정 → 같은 값이면 바이트 단위로 같음)."""
        return self.model_dump_json(by_alias=True)


# --- API-020 chunkSpec (API 계약값; 판정 기준값이 아니므로 카탈로그가 아니라 여기 둔다) ---


class ChunkSpec(ApiModel):
    """세션 시작 때 서버가 내려주는 청크 규격 (SPEC 1장 API-020)."""

    max_frames: int = 300
    max_bytes: int = 262144
    fps: int = 15


CHUNK_SPEC = ChunkSpec()

#: 정규화 좌표 허용 범위. MediaPipe는 화면 밖 관절에 [0,1]을 조금 벗어난 값을 낸다
#: (DECISIONS.md D-08). 판정 기준값이 아니라 입력 형식 검증용이다.
COORD_MIN = -1.0
COORD_MAX = 2.0


# --- 입력 --------------------------------------------------------------------


class Landmark(ApiModel):
    """관절 1개. 정규화 이미지 좌표 (y는 아래로 증가).

    - `visibility`: MediaPipe는 visibility, MoveNet은 keypoint score를 그대로 넣는다 (0~1).
    - `z`: MediaPipe 상대 깊이. MoveNet은 null. 엔진은 z를 쓰지 않는다.
    """

    x: float = Field(ge=COORD_MIN, le=COORD_MAX)
    y: float = Field(ge=COORD_MIN, le=COORD_MAX)
    z: float | None = None
    visibility: float = Field(ge=0.0, le=1.0)


class Frame(ApiModel):
    """한 프레임.

    - `t`: 세션 시작 기준 ms, 단조 증가.
    - `landmarks`: 모델 원본 순서의 관절 배열(MediaPipe 33 / MoveNet 17). null = 사람 미검출.
      얼굴 인덱스(MediaPipe 0~10, MoveNet 0~4)는 반드시 null이어야 한다 (US-01).
      얼굴 외 관절이 null이면 visibility 0으로 취급한다.
    """

    t: int = Field(ge=0)
    landmarks: list[Landmark | None] | None


class Chunk(ApiModel):
    """업로드 청크. seq는 0부터 연속."""

    session_id: str = Field(min_length=1)
    seq: int = Field(ge=0)
    frames: list[Frame]


class Platform(StrEnum):
    IOS = "IOS"
    ANDROID = "ANDROID"


class Device(ApiModel):
    """기기 정보.

    `model_version`은 자세 추정 모델 식별자이며 서버가 어댑터를 고르는 데 쓴다.
    형식: `<family>-<variant>[@<version>]` (예: `mediapipe-pose-lite@0.10`, `movenet-lightning@4`).
    """

    platform: Platform
    model_version: str = Field(min_length=1)


class LivenessAction(StrEnum):
    RAISE_LEFT_HAND = "RAISE_LEFT_HAND"
    RAISE_RIGHT_HAND = "RAISE_RIGHT_HAND"
    RAISE_BOTH_HANDS = "RAISE_BOTH_HANDS"


class LivenessChallenge(ApiModel):
    """세션에 발급된 무작위 동작 확인 (시각은 세션 기준 ms)."""

    challenge_id: str = Field(min_length=1)
    action: LivenessAction
    issued_at_t: int = Field(ge=0)
    expires_at_t: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_window(self) -> LivenessChallenge:
        if self.expires_at_t <= self.issued_at_t:
            raise ValueError("expiresAtT는 issuedAtT보다 커야 함")
        return self


class SessionMeta(ApiModel):
    """세션 메타."""

    session_id: str = Field(min_length=1)
    exercise_type: Literal["SQUAT"]
    catalog_version: str = Field(min_length=1)
    fps: int = Field(gt=0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    mirrored: bool
    device: Device
    liveness: LivenessChallenge | None = None


# --- 출력 --------------------------------------------------------------------


class RepReason(StrEnum):
    """렙 미인정 사유 (우선순위: OUT_OF_FRAME > TOO_FAST > SHALLOW_DEPTH)."""

    OUT_OF_FRAME = "OUT_OF_FRAME"
    TOO_FAST = "TOO_FAST"
    SHALLOW_DEPTH = "SHALLOW_DEPTH"


class RepEvent(ApiModel):
    """시도로 기록된 렙 1개 (인정·미인정 모두).

    각도는 도(°, 소수 1자리), 시각은 세션 기준 ms, 비율은 0~1(소수 3자리).
    `kneeAsymmetryAtBottom`은 최저점에서 양다리가 모두 보이지 않으면 null.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_knee_angle: float
    max_hip_drop: float | None
    trunk_lean_at_bottom: float | None
    knee_asymmetry_at_bottom: float | None
    invalid_ratio: float


class LivenessStatus(StrEnum):
    PASSED = "PASSED"
    EXPIRED = "EXPIRED"
    FAILED_NO_PERSON = "FAILED_NO_PERSON"


class LivenessEvidence(ApiModel):
    """판정 근거. 시간은 ms, 비율은 0~1.

    `wrongHandDetected`는 SPEC 6.2 "반대 손을 wrong_hand_hold_ms 이상 든 경우 기록"을 위한
    추가 필드다 (DECISIONS D-26).
    """

    max_hold_ms: int
    wrong_hand_max_hold_ms: int
    valid_frame_ratio: float
    wrong_hand_detected: bool


class LivenessResult(ApiModel):
    challenge_id: str
    action: LivenessAction
    status: LivenessStatus
    passed_at_t: int | None
    evidence: LivenessEvidence


class IssuedChallenge(ApiModel):
    """새로 발급한 무작위 동작 (POST /internal/liveness/issue 응답)."""

    action: LivenessAction
    instruction: str
    challenge_id: str


class ConfidenceComponents(ApiModel):
    """확신도 원시 구성요소 (0~1, 소수 3자리). 디버깅·검수용."""

    vis: float
    valid: float
    track: float
    consistency: float
    unaccepted: float
    raw: float
    liveness_penalty_applied: bool
    active_start_t: int | None
    active_end_t: int | None


class ConfidenceResult(ApiModel):
    ai_confidence: float
    components: ConfidenceComponents


class AvgMinMax(ApiModel):
    avg: float
    min: float
    max: float


class AvgMax(ApiModel):
    avg: float
    max: float


class AvgOnly(ApiModel):
    avg: float


class AvgStd(ApiModel):
    avg: float
    std: float


class FormTag(StrEnum):
    """자세 오류 태그 (LLM L4가 수치 없이 코멘트할 수 있게). SPEC 8.2 — 제안·팀 합의 필요."""

    SHALLOW_DEPTH_FREQUENT = "SHALLOW_DEPTH_FREQUENT"
    DEPTH_INCONSISTENT = "DEPTH_INCONSISTENT"
    TRUNK_LEAN_EXCESSIVE = "TRUNK_LEAN_EXCESSIVE"
    KNEE_ASYMMETRY = "KNEE_ASYMMETRY"
    TEMPO_TOO_FAST = "TEMPO_TOO_FAST"
    FREQUENT_OUT_OF_FRAME = "FREQUENT_OUT_OF_FRAME"


class PoseSummary(ApiModel):
    """인정 렙 최저점 기준 자세 요약 (L4 입력). 인정 렙이 0개면 수치 필드는 null.

    `kneeFlexionDeg` = 180 − minKneeAngle (펴면 0°, DECISIONS D-29).
    """

    knee_flexion_deg: AvgMinMax | None
    trunk_lean_deg: AvgMax | None
    knee_asymmetry_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyCode(StrEnum):
    REP_TIMING_TOO_REGULAR = "REP_TIMING_TOO_REGULAR"
    LANDMARKS_FROZEN = "LANDMARKS_FROZEN"
    ZERO_JITTER = "ZERO_JITTER"
    BODY_PROPORTION_SHIFT = "BODY_PROPORTION_SHIFT"
    MULTIPLE_RESETS = "MULTIPLE_RESETS"
    UNREALISTIC_PACE = "UNREALISTIC_PACE"
    CLIENT_CONFIDENCE_DIVERGENCE = "CLIENT_CONFIDENCE_DIVERGENCE"


class Anomaly(ApiModel):
    """규칙 기반 이상 징후 (L2 입력). `detail`은 사람이 읽는 설명."""

    code: AnomalyCode
    severity: Severity
    detail: str


class SessionResult(ApiModel):
    """서버(또는 기기)가 세션 하나를 판정한 결과 (SPEC 9.1)."""

    engine_version: str
    catalog_version: str
    reps: list[RepEvent]
    recognized_reps: int
    attempted_reps: int
    liveness: LivenessResult | None
    ai_confidence: float
    confidence_components: ConfidenceComponents
    pose_summary: PoseSummary
    anomalies: list[Anomaly]


class ClientRep(BaseModel):
    """클라이언트가 제출한 렙 (API-026 `reps[]`). 대조에 필요한 필드만 읽고 나머지는 무시한다."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    start_t: int = Field(ge=0)
    end_t: int = Field(ge=0)
    accepted: bool
    reason: RepReason | None = None


class ClientSubmission(ApiModel):
    """클라이언트 제출값 (API-026). 확신도·요약은 기록·비교용으로만 쓴다."""

    client_rep_count: int = Field(ge=0)
    reps: list[ClientRep] = Field(default_factory=list)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    pose_summary: dict[str, Any] | None = None


class RecountComparison(ApiModel):
    """서버 재계산과 클라이언트 제출값 비교 (SPEC 9.2).

    `finalRepCount`가 인정량이다 (항상 서버 값 이하). `errorCode`가
    `SERVER_RECOUNT_MISMATCH`여도 HTTP는 200이며, 최종 처리는 백엔드가 한다.
    """

    server_rep_count: int
    client_rep_count: int
    user_reduced_count: int | None
    final_rep_count: int
    mismatch: bool
    mismatch_ratio: float
    error_code: Literal["SERVER_RECOUNT_MISMATCH"] | None
    matched_reps: int
    client_only_reps: int
    server_only_reps: int
    accepted_disagreements: int
    server_confidence: float
    client_confidence: float
    confidence_diff: float
    anomalies: list[Anomaly]


class ApprovalReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LIVENESS_NOT_PASSED = "LIVENESS_NOT_PASSED"
    RECOUNT_MISMATCH = "RECOUNT_MISMATCH"
    ANOMALY_HIGH = "ANOMALY_HIGH"


class ApprovalEvidence(ApiModel):
    server_confidence: float
    auto_approve_threshold: float
    liveness_status: LivenessStatus | None
    liveness_policy: Literal["restart", "review"]
    mismatch: bool
    high_anomalies: list[AnomalyCode]


class ApprovalDecision(ApiModel):
    """자동 승인 판정 (SPEC 9.3). 제출건 상태는 바꾸지 않는다 — 상태 전이는 백엔드가 한다.

    `approvalPath`: `AI_AUTO`(DATA-MODEL.md 값) / `HUMAN_REVIEW` / `RESTART` (DECISIONS D-37).
    """

    decision: Literal["AUTO_APPROVE", "HUMAN_REVIEW", "REJECT_RESTART"]
    approval_path: Literal["AI_AUTO", "HUMAN_REVIEW", "RESTART"]
    reason_codes: list[ApprovalReason]
    evidence: ApprovalEvidence
