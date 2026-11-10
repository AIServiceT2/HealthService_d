"""길드 API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

from app.modules.guild.models import NAME_MAX_LENGTH, NAME_MIN_LENGTH

# 노션 API-009: name은 2~20자. 앞뒤 공백을 지운 뒤 센다
GuildName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH),
]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class GuildCreate(_CamelModel):
    """API-009 요청: { name }."""

    name: GuildName


class GuildCreated(_CamelModel):
    """API-009 응답 201: { guildId, name, leaderUserId }."""

    guild_id: uuid.UUID
    name: str
    leader_user_id: uuid.UUID


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | None = None
