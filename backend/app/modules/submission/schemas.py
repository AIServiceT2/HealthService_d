"""제출건 API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from datetime import datetime
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    # 입력 오류(400)는 항목 목록(list), 그 밖의 에러는 객체이거나 null (app/core/errors.py)
    details: dict | list | None = None


# ---- API-026 세션 종료·운동 제출 ----


class RepIn(_CamelModel):
    model_config = ConfigDict(extra="forbid")

    rep_no: int = Field(ge=1)
    ts: AwareDatetime
    counted: bool


class SubmitRequest(_CamelModel):
    """{ totalChunks, endedAt, clientRepCount, reps, aiConfidence }."""

    model_config = ConfigDict(extra="forbid")

    total_chunks: int = Field(ge=1)
    ended_at: AwareDatetime
    client_rep_count: int = Field(ge=0)
    reps: list[RepIn]
    ai_confidence: float = Field(ge=0, le=1)


class SubmitResponse(_CamelModel):
    """API-026 응답 202: { submissionId, status, countedReps, reservedReps, version }."""

    submission_id: uuid.UUID
    status: str
    counted_reps: int
    reserved_reps: int
    version: int


# ---- API-028 제출 상태 조회 ----


class SubmissionDetailRead(_CamelModel):
    """API-028 응답 200 (API-029 목록 항목도 같은 형식)."""

    id: uuid.UUID
    session_id: uuid.UUID
    exercise_code: str
    # SUBMITTED~REVOKED 9개 상태
    status: str
    version: int
    # AI_AUTO | REVIEWER, 승인 전 null
    approval_path: str | None
    started_at: datetime
    ended_at: datetime
    counted_reps: int
    reserved_reps: int
    confidence: float
    liveness_passed: bool | None
