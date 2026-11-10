"""llm API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from app.modules.llm.rules import POSE_SUMMARY_MAX_JOINTS


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorResponse(_CamelModel):
    """공통 에러 본문 (app/core/errors.py). Swagger 표시용."""

    code: str
    message: str
    details: Any = None


# ---- API-049 L3 전투 서사 ----


class NarrativeRequest(_CamelModel):
    submission_id: uuid.UUID


class GeneratedText(_CamelModel):
    level: str
    text: str
    is_fallback: bool


# ---- API-050 L4 자세 교정 코멘트 ----


class AngleStats(_CamelModel):
    """관절 각도 요약 통계(도). 관절 좌표 원본은 받지 않는다 (노션 API-050, STACK.md L4 입력)."""

    avg: float = Field(ge=0, le=180)
    min: float | None = Field(default=None, ge=0, le=180)
    max: float | None = Field(default=None, ge=0, le=180)


JointName = Annotated[str, StringConstraints(pattern=r"^[a-z][A-Za-z]{0,31}$")]


class FormCommentRequest(_CamelModel):
    submission_id: uuid.UUID
    # 키는 관절 이름(kneeAngle 등). 입력 계약이 미정이라 이름은 형식만 검사한다
    pose_summary: dict[JointName, AngleStats] = Field(max_length=POSE_SUMMARY_MAX_JOINTS)


# ---- API-051 L1 기록 요약·L2 이상치 설명 ----


class ReviewSummaryRequest(_CamelModel):
    submission_id: uuid.UUID


class AnomalyRead(_CamelModel):
    type: str
    rep_nos: list[int]
    description: str


class ReviewSummaryResponse(_CamelModel):
    summary: str
    anomalies: list[AnomalyRead]
