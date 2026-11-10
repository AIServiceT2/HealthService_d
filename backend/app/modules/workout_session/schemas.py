"""session API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- API-018 운동 목록 ----


class ExerciseCriteria(_CamelModel):
    # 가동범위 수치는 미정이라 null (노션 API-018). 엔진 가안 값은 ai/config/catalog에 있음
    knee_angle_max: float | None = None


class ExerciseItem(_CamelModel):
    code: str
    name: str
    daily_cap: int
    criteria: ExerciseCriteria
    recommended_camera_angle: str | None = None  # 권장 촬영 각도 미정 (PRD 미정 표)
    tutorial_url: str | None = None  # 튜토리얼 자료 없음


class ExercisesResponse(_CamelModel):
    catalog_version: str
    items: list[ExerciseItem]


# ---- API-019 내 일일 상한 ----


class DailyCapItem(_CamelModel):
    exercise_code: str
    cap: int
    reserved: int
    remaining: int


class DailyCapsResponse(_CamelModel):
    date: date
    items: list[DailyCapItem]


# ---- API-020 운동 세션 시작 ----


class GoalIn(_CamelModel):
    reps: int = Field(ge=1)
    sets: int = Field(ge=1)


class TargetIn(_CamelModel):
    # 데모 공략 대상(던전 적 / 주간 보스)은 미정 (PRD 미정 표). 대상 테이블이 없어 id는 검사하지 않음
    type: Literal["DUNGEON", "BOSS"]
    id: uuid.UUID


class DeviceIn(_CamelModel):
    # 명세 예시 필드. 저장할 칼럼이 ERD에 없어 받기만 한다 [팀 확인 필요]
    os: str = Field(max_length=32)
    model: str = Field(max_length=64)


class StartSessionRequest(_CamelModel):
    exercise_code: str = Field(max_length=32)
    # ERD에서 goal·target은 NULL 허용이라 선택으로 받는다
    goal: GoalIn | None = None
    target: TargetIn | None = None
    device: DeviceIn | None = None


class LivenessChallengeOut(_CamelModel):
    challenge_id: uuid.UUID
    action: str
    timeout_sec: int


class ChunkSpecOut(_CamelModel):
    max_frames: int
    max_bytes: int


class StartSessionResponse(_CamelModel):
    session_id: uuid.UUID
    status: str
    catalog_version: str
    remaining_daily_cap: int
    liveness: LivenessChallengeOut
    chunk_spec: ChunkSpecOut


# ---- API-021 무작위 동작 확인 결과 ----


class LivenessRequest(_CamelModel):
    challenge_id: uuid.UUID
    detected_action: str = Field(max_length=32)
    # 판정 기준이 미정이라 범위만 검사하고 판정에는 쓰지 않음 (service.submit_liveness)
    score: float = Field(ge=0, le=1)
    detected_at: datetime


class LivenessResponse(_CamelModel):
    passed: bool
    retry_allowed: bool


# ---- API-022 관절 좌표 청크 업로드 ----

# [x, y, visibility]. 얼굴 랜드마크 자리와 안 보이는 관절은 null
Keypoint = Annotated[list[float], Field(min_length=3, max_length=3)] | None


class FrameIn(_CamelModel):
    t: int = Field(ge=0)  # 프레임 시각 (epoch ms, 노션 예시)
    kp: list[Keypoint]


class PoseChunkRequest(_CamelModel):
    seq: int = Field(ge=1)
    frames: list[FrameIn] = Field(min_length=1)


class PoseChunkResponse(_CamelModel):
    received: list[int]


# ---- API-023 세션 일시중지 ----


class PauseRequest(_CamelModel):
    # 저장할 칼럼이 ERD에 없어 받기만 한다 [팀 확인 필요]
    reason: Literal["CAMERA_LOST", "APP_BACKGROUND"]
    at: datetime


class SessionStatusResponse(_CamelModel):
    session_id: uuid.UUID
    status: str


# ---- API-024 세션 재개 ----


class ResumeResponse(SessionStatusResponse):
    received_chunks: list[int]  # 빠진 seq부터 다시 보내면 된다
