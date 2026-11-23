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


#: 엔진이 판정하는 종목. 영문 값 표기는 제안·팀 확인 필요 (DATA-MODEL.md '아직 정하지 못한 것',
#: DECISIONS D-66·D-71~D-73·D-83~D-86).
#: MVP 범위(mvp-scope.md)는 스쿼트뿐이며 나머지 종목은 엔진에만 있다.
ExerciseType = Literal[
    "SQUAT",
    "PUSHUP",
    "SITUP",
    "LUNGE",
    "INVERTED_SHOULDER_PRESS",
    "GLUTE_BRIDGE",
    "SIDE_LEG_LIFT",
    "HIGH_KNEE",
    "MOUNTAIN_CLIMBER",
    "SUPERMAN",
    "DONKEY_KICK",
]


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
    exercise_type: ExerciseType
    catalog_version: str = Field(min_length=1)
    fps: int = Field(gt=0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    mirrored: bool
    device: Device
    liveness: LivenessChallenge | None = None


# --- 출력 --------------------------------------------------------------------


class RepReason(StrEnum):
    """렙 미인정 사유 (우선순위: OUT_OF_FRAME > TOO_FAST > SHALLOW_DEPTH).

    `SHALLOW_DEPTH`는 모든 종목에서 "가동범위 기준 미달"이다 (푸시업: 덜 내려감,
    윗몸 일으키기: 덜 일어남).
    """

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

    @property
    def depth_angle(self) -> float:
        """가동범위 판정 각도의 최저값 (종목 공통 이름, 직렬화되지 않음)."""
        return self.min_knee_angle


class PushupRepEvent(ApiModel):
    """푸시업 렙 1개 (인정·미인정 모두). 판정 각도는 팔꿈치 내각(어깨–팔꿈치–손목, 도).

    - `bottomT`: 팔꿈치 각도가 가장 작은 시각.
    - `bodyLineDevAtBottom`: 180 − (어깨–엉덩이–발목 내각). 몸이 일직선이면 0°, 허리가 처지거나
      엉덩이가 들리면 커진다. 해당 관절이 안 보이면 null.
    - `elbowAsymmetryAtBottom`: 좌우 팔꿈치 각도 차. 양팔이 모두 보일 때만.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_elbow_angle: float
    body_line_dev_at_bottom: float | None
    elbow_asymmetry_at_bottom: float | None
    invalid_ratio: float
    #: 렙 동안 무릎 내각의 최저값 (D-78). 무릎을 대고 하면 작다. 다리가 안 보였으면 null
    min_knee_angle_in_rep: float | None = None

    @property
    def depth_angle(self) -> float:
        return self.min_elbow_angle


class SitupRepEvent(ApiModel):
    """윗몸 일으키기 렙 1개. 두 각도가 모두 기준을 넘어야 인정한다 (DECISIONS D-70).

    - `minTorsoAngle`: 상체 각도(어깨–엉덩이–발목 내각)의 최저값. 누우면 약 180°,
      상체가 바닥에서 x° 들리면 180 − x.
    - `minHipAngle`: 렙 동안 엉덩이 각도(어깨–엉덩이–무릎 내각)의 최저값.
      무릎이 한 번도 안 보였으면 null (그 렙은 OUT_OF_FRAME).
    - `bottomT`: 상체 각도가 가장 작은 시각 (가장 많이 일어난 시점).
    - `kneeAngleAtBottom`: 그때의 무릎 내각(엉덩이–무릎–발목). 무릎이 안 보이면 null.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_torso_angle: float
    min_hip_angle: float | None
    knee_angle_at_bottom: float | None
    invalid_ratio: float
    #: 렙 동안 발이 바닥에서 뜬 최대 높이 ÷ 다리 길이 (D-82). 발 뜸 규칙이 없는 카탈로그면 null
    max_foot_lift: float | None = None

    @property
    def depth_angle(self) -> float:
        return self.min_torso_angle


class LungeRepEvent(ApiModel):
    """런지 렙 1개 (D-71). 판정 각도는 무릎 내각(엉덩이–무릎–발목, 보이는 다리 평균, 도).

    - `hipSpreadAtBottom`: 최저점의 |왼쪽 − 오른쪽 엉덩이 내각(어깨–엉덩이–무릎)|. 런지는 앞다리
      엉덩이가 굽고 뒷다리 엉덩이가 펴져서 크고, 스쿼트는 0에 가깝다. 양쪽이 다 보이지 않으면 null
      (그 렙은 OUT_OF_FRAME).
    - `kneeAsymmetryAtBottom`: 좌우 무릎 각도 차. 양다리가 모두 보일 때만.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_knee_angle: float
    hip_spread_at_bottom: float | None
    knee_asymmetry_at_bottom: float | None
    invalid_ratio: float
    #: 렙 시작 직전~끝 동안 발이 바닥에서 뜬 최대 높이 ÷ 다리 길이 (D-79). 잴 수 없으면 null
    max_foot_lift: float | None

    @property
    def depth_angle(self) -> float:
        return self.min_knee_angle


class InvertedShoulderPressRepEvent(ApiModel):
    """인버티드 숄더 프레스(파이크 자세) 렙 1개 (D-72). 판정 각도는 팔꿈치 내각(도).

    - `minPikeHipAngle`: 렙 동안 엉덩이 각도(어깨–엉덩이–발목 내각)의 최저값. 엉덩이를 높이 접을수록
      작다(일반 푸시업은 약 180°). 한 번도 안 보였으면 null (그 렙은 OUT_OF_FRAME).
    - `kneeAngleAtBottom`: 최저점의 무릎 내각. 다리를 펴면 약 180°.
    - `elbowAsymmetryAtBottom`: 좌우 팔꿈치 각도 차. 양팔이 모두 보일 때만.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_elbow_angle: float
    min_pike_hip_angle: float | None
    knee_angle_at_bottom: float | None
    elbow_asymmetry_at_bottom: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        return self.min_elbow_angle


class GluteBridgeRepEvent(ApiModel):
    """글루트 브릿지 렙 1개 (D-73).

    - `minHipFlexion`: 렙 동안 엉덩이 굽힘(180 − 어깨–엉덩이–무릎 내각)의 최저값. 엉덩이를 들어
      어깨–엉덩이–무릎이 일직선이면 0°. 누운 자세는 약 45°.
    - `bottomT`: 판정 각도가 가장 작은 시각 = 엉덩이가 가장 높이 들린 시각 (종목 공통 이름).
    - `kneeAngleAtTop`: 그때의 무릎 내각(엉덩이–무릎–발목). 안 보이면 null.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_hip_flexion: float
    knee_angle_at_top: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        return self.min_hip_flexion


class SideLegLiftRepEvent(ApiModel):
    """사이드 레그 리프트 렙 1개 (D-77).

    - `maxLegSpread`: 렙 동안 다리 벌림(왼·오른 엉덩이→발목 선 사이 각도)의 최댓값(도).
      다리를 모으면 약 0°.
    - `bottomT`: 다리를 가장 높이 든 시각 (종목 공통 이름).
    - `kneeAngleAtTop`: 그때의 무릎 내각(보이는 다리 평균). 다리를 펴면 약 180°.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    max_leg_spread: float
    knee_angle_at_top: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        """판정 각도(180 − 다리 벌림)의 최저값."""
        return 180.0 - self.max_leg_spread


class HighKneeRepEvent(ApiModel):
    """하이 니 렙 1개 = 왼다리 1번 + 오른다리 1번 (D-83). 두 다리가 모두 인정이어야 인정.

    - `leftMinHipAngle`·`rightMinHipAngle`: 다리별 엉덩이 내각(어깨–엉덩이–무릎) 최저값. 서 있으면
      약 180°, 무릎을 엉덩이 높이까지 올리면 약 90°.
    - `leftReason`·`rightReason`: 다리별 미인정 사유 (인정이면 null).
      `reason`은 둘 중 우선순위가 높은 것.
    - `minStandingHipAngle`: 각 다리를 올린 순간 반대(서 있는) 다리 엉덩이 내각 중 작은 값.
      못 쟀으면 null.
    - `startT` = 앞 다리 시작, `endT` = 뒷 다리 끝, `bottomT` = 더 높이 올린 다리의 최고점 시각.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    left_min_hip_angle: float
    right_min_hip_angle: float
    left_reason: RepReason | None
    right_reason: RepReason | None
    min_standing_hip_angle: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        """덜 올린 다리의 엉덩이 내각 (가동범위 판정은 두 다리 모두 넘어야 하므로)."""
        return max(self.left_min_hip_angle, self.right_min_hip_angle)


class MountainClimberRepEvent(ApiModel):
    """마운틴 클라이머 렙 1개 = 왼다리 1번 + 오른다리 1번 (D-84). 두 다리가 모두 인정이어야 인정.

    - `leftMinTuckAngle`·`rightMinTuckAngle`: 다리별 엉덩이 내각(어깨–엉덩이–무릎) 최저값.
      플랭크에서 약 180°, 무릎을 가슴 쪽으로 당길수록 작다.
    - `minBackLegHipAngle`: 각 다리를 당긴 순간 반대(뒤로 뻗은) 다리 엉덩이 내각 중 작은 값.
    - `minArmSupportAngle`: 렙 동안 팔 지지 각도 최저값 (손을 어깨 아래 바닥에 짚으면 약 180°).
      팔이 안 보였으면 null.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    left_min_tuck_angle: float
    right_min_tuck_angle: float
    left_reason: RepReason | None
    right_reason: RepReason | None
    min_back_leg_hip_angle: float | None
    min_arm_support_angle: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        return max(self.left_min_tuck_angle, self.right_min_tuck_angle)


class SupermanRepEvent(ApiModel):
    """슈퍼맨 렙 1개 (D-85). 들었다 내리면 1렙.

    - `minBodyArchAngle`: 몸 활 각도(어깨–엉덩이–발목 내각) 최저값. 엎드려 일직선이면 약 180°.
    - `bottomT`: 가장 높이 든 시각 (종목 공통 이름).
    - `armReachAtTop`: 그때의 팔 뻗음(엉덩이–어깨–손목 내각). 팔을 머리 위로 뻗으면 약 180°.
      안 보이면 null (그 렙은 OUT_OF_FRAME).
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    min_body_arch_angle: float
    arm_reach_at_top: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        return self.min_body_arch_angle


class DonkeyKickRepEvent(ApiModel):
    """돈키 킥 렙 1개 (D-86). 한쪽 다리를 뒤로 차 올렸다 내리면 1렙.

    - `maxKickHipAngle`: 렙 동안 찬 다리의 엉덩이 내각(어깨–엉덩이–무릎) 최댓값. 네발 자세 약 90°,
      허벅지가 몸통과 일직선이면 약 180°.
    - `kneeAngleAtTop`: 가장 높이 찬 순간의 무릎 내각(보이는 다리 평균). 안 보이면 null.
    - `minArmSupportAngle`: 렙 동안 팔 지지 각도 최저값. 팔이 안 보였으면 null.
    """

    index: int = Field(ge=1)
    start_t: int
    bottom_t: int
    end_t: int
    accepted: bool
    reason: RepReason | None
    max_kick_hip_angle: float
    knee_angle_at_top: float | None
    min_arm_support_angle: float | None
    invalid_ratio: float

    @property
    def depth_angle(self) -> float:
        """판정 각도(180 − 엉덩이 내각)의 최저값."""
        return 180.0 - self.max_kick_hip_angle


#: 세션 결과의 렙 (종목별 모양). 필드 이름이 서로 달라 JSON만으로 구별된다.
AnyRepEvent = (
    RepEvent
    | PushupRepEvent
    | SitupRepEvent
    | LungeRepEvent
    | InvertedShoulderPressRepEvent
    | GluteBridgeRepEvent
    | SideLegLiftRepEvent
    | HighKneeRepEvent
    | MountainClimberRepEvent
    | SupermanRepEvent
    | DonkeyKickRepEvent
)


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
    #: 푸시업: 몸이 일직선에서 벗어남 (허리 처짐·엉덩이 들림). 제안·팀 합의 필요 (D-66)
    BODY_LINE_BROKEN = "BODY_LINE_BROKEN"
    #: 푸시업: 좌우 팔꿈치 각도 차가 큼. 제안·팀 합의 필요 (D-66)
    ELBOW_ASYMMETRY = "ELBOW_ASYMMETRY"


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


class PushupPoseSummary(ApiModel):
    """푸시업 자세 요약 (L4 입력). 인정 렙 최저점 기준, 인정 렙이 0개면 수치 필드는 null.

    `elbowFlexionDeg` = 180 − minElbowAngle (팔을 펴면 0°).
    """

    elbow_flexion_deg: AvgMinMax | None
    body_line_dev_deg: AvgMax | None
    elbow_asymmetry_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class SitupPoseSummary(ApiModel):
    """윗몸 일으키기 자세 요약 (L4 입력). 인정 렙이 0개면 수치 필드는 null.

    - `torsoRaiseDeg` = 180 − minTorsoAngle (상체가 바닥에서 들린 각도).
    - `hipFlexionDeg` = 180 − minHipAngle (상체를 무릎 쪽으로 접은 정도).
    """

    torso_raise_deg: AvgMinMax | None
    hip_flexion_deg: AvgMinMax | None
    knee_angle_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class LungePoseSummary(ApiModel):
    """런지 자세 요약 (L4 입력, D-71). 인정 렙이 0개면 수치 필드는 null.

    - `lungeKneeFlexionDeg` = 180 − minKneeAngle.
    - `hipSpreadDeg`: 최저점의 좌우 엉덩이 각도 차 (보폭이 충분했는지).
    """

    lunge_knee_flexion_deg: AvgMinMax | None
    hip_spread_deg: AvgMinMax | None
    knee_asymmetry_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class InvertedShoulderPressPoseSummary(ApiModel):
    """인버티드 숄더 프레스 자세 요약 (L4 입력, D-72). 인정 렙이 0개면 수치 필드는 null.

    - `elbowFlexionDeg` = 180 − minElbowAngle.
    - `pikeHipAngleDeg`: 렙별 엉덩이 각도 최저값 (작을수록 엉덩이를 높이 접음).
    - `kneeAngleDeg`: 최저점 무릎 내각 (다리를 펴면 약 180°).
    """

    elbow_flexion_deg: AvgMinMax | None
    pike_hip_angle_deg: AvgMinMax | None
    knee_angle_deg: AvgOnly | None
    elbow_asymmetry_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class GluteBridgePoseSummary(ApiModel):
    """글루트 브릿지 자세 요약 (L4 입력, D-73). 인정 렙이 0개면 수치 필드는 null.

    - `topHipFlexionDeg`: 렙별 엉덩이 굽힘 최저값 (0° = 어깨–엉덩이–무릎 일직선).
    - `topKneeAngleDeg`: 가장 높이 들었을 때의 무릎 내각.
    """

    top_hip_flexion_deg: AvgMinMax | None
    top_knee_angle_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class SideLegLiftPoseSummary(ApiModel):
    """사이드 레그 리프트 자세 요약 (L4 입력, D-77). 인정 렙이 0개면 수치 필드는 null.

    - `legSpreadDeg`: 렙별 다리 벌림 최댓값.
    - `topKneeAngle`: 가장 높이 들었을 때의 무릎 내각 (다리를 폈는지).
    """

    leg_spread_deg: AvgMinMax | None
    top_knee_angle: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class HighKneePoseSummary(ApiModel):
    """하이 니 자세 요약 (L4 입력, D-83). 인정 렙이 0개면 수치 필드는 null.

    - `kneeDriveDeg` = 180 − 다리별 엉덩이 내각 최저값 (인정 렙의 왼·오른 다리 모두).
    - `legAsymmetryDeg`: 렙마다 |왼 − 오른 엉덩이 내각 최저값|의 평균.
    - `standingHipAngleDeg`: 올린 순간 서 있는 다리의 엉덩이 내각 (렙별 작은 값).
    """

    knee_drive_deg: AvgMinMax | None
    leg_asymmetry_deg: AvgOnly | None
    standing_hip_angle_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class MountainClimberPoseSummary(ApiModel):
    """마운틴 클라이머 자세 요약 (L4 입력, D-84). 인정 렙이 0개면 수치 필드는 null.

    - `kneeTuckDeg` = 180 − 다리별 엉덩이 내각 최저값.
    - `legAsymmetryDeg`: 렙마다 |왼 − 오른|의 평균.
    - `backLegHipAngleDeg`: 당긴 순간 뒤로 뻗은 다리의 엉덩이 내각.
    - `armSupportDeg`: 렙별 팔 지지 각도 최저값의 평균.
    """

    knee_tuck_deg: AvgMinMax | None
    leg_asymmetry_deg: AvgOnly | None
    back_leg_hip_angle_deg: AvgOnly | None
    arm_support_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class SupermanPoseSummary(ApiModel):
    """슈퍼맨 자세 요약 (L4 입력, D-85). 인정 렙이 0개면 수치 필드는 null.

    - `bodyArchDeg` = 180 − 몸 활 각도 최저값 (얼마나 휘었는지).
    - `armReachDeg`: 가장 높이 든 순간 팔 뻗음.
    """

    body_arch_deg: AvgMinMax | None
    arm_reach_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


class DonkeyKickPoseSummary(ApiModel):
    """돈키 킥 자세 요약 (L4 입력, D-86). 인정 렙이 0개면 수치 필드는 null.

    - `kickHipAngleDeg`: 렙별 찬 다리 엉덩이 내각 최댓값 (180° = 허벅지가 몸통과 일직선).
    - `kickKneeAngleDeg`: 가장 높이 찬 순간 무릎 내각.
    """

    kick_hip_angle_deg: AvgMinMax | None
    kick_knee_angle_deg: AvgOnly | None
    rep_duration_ms: AvgStd | None
    depth_consistency_deg: float | None
    form_tags: list[FormTag]


AnyPoseSummary = (
    PoseSummary
    | PushupPoseSummary
    | SitupPoseSummary
    | LungePoseSummary
    | InvertedShoulderPressPoseSummary
    | GluteBridgePoseSummary
    | SideLegLiftPoseSummary
    | HighKneePoseSummary
    | MountainClimberPoseSummary
    | SupermanPoseSummary
    | DonkeyKickPoseSummary
)


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
    reps: list[AnyRepEvent]
    recognized_reps: int
    attempted_reps: int
    liveness: LivenessResult | None
    ai_confidence: float
    confidence_components: ConfidenceComponents
    pose_summary: AnyPoseSummary
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
