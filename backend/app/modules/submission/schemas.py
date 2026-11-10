"""제출건 API 입출력. 노션 API 명세서의 API는 camelCase, 첫 기능(US-02)의 SubmissionRead는 기존 형식."""

import uuid
from datetime import datetime
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class SubmissionRead(BaseModel):
    """첫 기능(US-02)의 임시 응답. API-028로 바꿀 때 지운다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    exercise_type: str = Field(validation_alias="exercise_code")
    counted_reps: int


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
