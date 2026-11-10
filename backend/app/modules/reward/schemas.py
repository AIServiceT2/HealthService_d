"""지급 API 입출력. JSON 키는 노션 API 명세서대로 camelCase."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ItemRef(_CamelModel):
    item_id: uuid.UUID
    status: str


class DamageRead(_CamelModel):
    """targetType·targetId는 세션에서 고른 공략 대상 (고르지 않았으면 null)."""

    target_type: str | None
    target_id: uuid.UUID | None
    amount: int


class AppliedRead(_CamelModel):
    exp: int
    items: list[ItemRef]
    damage: DamageRead


class GrantResponse(_CamelModel):
    """API-041 응답 200: { submissionId, alreadyGranted, applied, rewardedAt }."""

    submission_id: uuid.UUID
    already_granted: bool
    applied: AppliedRead
    rewarded_at: datetime


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | list | None = None
