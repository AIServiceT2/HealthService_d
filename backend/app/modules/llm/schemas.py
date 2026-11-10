"""llm API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
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


# ---- API-049 L3 전투 서사 ----


class NarrativeRequest(_CamelModel):
    submission_id: uuid.UUID


class GeneratedText(_CamelModel):
    level: str
    text: str
    is_fallback: bool
