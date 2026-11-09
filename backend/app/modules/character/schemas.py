"""캐릭터 API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

# 선택 범위는 미정 (노션 API-006·008). 앞뒤 공백을 지운 뒤 1~32자. 공백만 있으면 400
AvatarId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class CharacterCreate(_CamelModel):
    """API-006 요청. avatarId는 선택이고 선택 범위는 미정 (노션 API-006)."""

    avatar_id: AvatarId | None = None


class CharacterUpdate(_CamelModel):
    """API-008 요청. 수정 가능한 필드는 미정이라 명세 예시의 avatarId만 받는다 (노션 API-008).

    level·exp 등 다른 필드를 보내면 400 (플레이어가 성장 수치를 직접 바꾸지 못하게).
    보내지 않은 필드는 바꾸지 않고, null을 보내면 아바타를 비운다.
    """

    model_config = ConfigDict(extra="forbid")

    avatar_id: AvatarId | None = None


class CharacterRead(_CamelModel):
    """API-006 응답 201 / API-008 응답 200: { userId, avatarId, exp, level }."""

    user_id: uuid.UUID
    avatar_id: str | None
    exp: int
    level: int


class ExpRead(_CamelModel):
    """confirmed: 확정 경험치, pending: 24시간 보호 기간 중인 경험치 (노션 API-007)."""

    confirmed: int
    pending: int


class MyCharacterRead(_CamelModel):
    """API-007 응답 200: { userId, avatarId, level, exp: {confirmed, pending}, stats, lockedItemCount }."""

    user_id: uuid.UUID
    avatar_id: str | None
    level: int
    exp: ExpRead
    # 능력치 축이 미정이라 빈 배열 (노션 API-007)
    stats: list = Field(default_factory=list)
    locked_item_count: int


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | None = None
