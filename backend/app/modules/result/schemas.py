"""결과 API 입출력. JSON 키는 노션 API 명세서대로 camelCase."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DropRead(_CamelModel):
    item_id: uuid.UUID
    status: str


class CardRead(_CamelModel):
    exercise_code: str
    counted_reps: int
    # 리플레이(API-048) 타격 수와 같다
    hit_count: int
    exp: int
    total_damage: int
    drops: list[DropRead]
    rewarded_at: datetime
    # 명세에 없는 필드 [추가·팀 확인 필요]: 타격 0이면 true → 리플레이 없이 '일일 상한 초과' 카드 (US-05)
    daily_cap_exceeded: bool


class TextRead(_CamelModel):
    level: str
    text: str
    is_fallback: bool


class ResultRead(_CamelModel):
    """API-047 응답 200: { card, narrative, formComment }."""

    card: CardRead
    narrative: TextRead
    form_comment: TextRead


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | list | None = None
