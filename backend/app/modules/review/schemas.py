"""review API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorResponse(_CamelModel):
    """공통 에러 본문 (app/core/errors.py). Swagger 표시용."""

    code: str
    message: str
    details: Any = None


# ---- API-033 자동 승인 판정 ----


class AutoApprovalResponse(_CamelModel):
    decision: str  # AUTO_APPROVED | NEEDS_REVIEW
    confidence: float
    threshold: float
    liveness_passed: bool | None
    submission_status: str
    approval_path: str | None
