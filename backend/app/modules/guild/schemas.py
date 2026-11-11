"""길드 API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from app.modules.guild.models import (
    INVITE_CODE_PATTERN,
    INVITE_DEFAULT_HOURS,
    INVITE_MAX_HOURS,
    INVITE_MIN_HOURS,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
)

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


class GuildLeader(_CamelModel):
    """API-010 응답의 leader: { userId, nickname }."""

    user_id: uuid.UUID
    nickname: str


class GuildRead(_CamelModel):
    """API-010 응답 200: { id, name, leader: { userId, nickname }, memberCount }."""

    id: uuid.UUID
    name: str
    leader: GuildLeader
    member_count: int


class GuildMemberRead(_CamelModel):
    """API-011 목록 항목: { userId, nickname, role }."""

    user_id: uuid.UUID
    nickname: str
    role: Literal["LEADER", "MEMBER"]


class GuildMemberList(_CamelModel):
    """API-011 응답 200: { items, nextCursor }. nextCursor가 null이면 마지막 쪽."""

    items: list[GuildMemberRead]
    next_cursor: str | None


class InvitationCreate(_CamelModel):
    """API-012 요청: { expiresInHours } (선택). 기본 72, 1~168 [제안·팀 확인 필요]."""

    model_config = ConfigDict(extra="forbid")

    expires_in_hours: int = Field(
        default=INVITE_DEFAULT_HOURS, ge=INVITE_MIN_HOURS, le=INVITE_MAX_HOURS, strict=True
    )


class InvitationCreated(_CamelModel):
    """API-012 응답 201: { inviteCode, expiresAt }."""

    invite_code: str
    expires_at: datetime


def _normalize_code(value: object) -> object:
    # 패턴 검사 전에 앞뒤 공백을 지우고 대문자로 바꾼다 (손으로 입력한 소문자도 받음).
    # 문자열이 아니면 그대로 넘겨 400이 되게 한다
    return value.strip().upper() if isinstance(value, str) else value


# 영문 대문자·숫자 6자
InviteCode = Annotated[
    str, BeforeValidator(_normalize_code), StringConstraints(pattern=INVITE_CODE_PATTERN)
]


class GuildJoin(_CamelModel):
    """API-013 요청: { inviteCode }."""

    invite_code: InviteCode


class RecommendedGuildRead(_CamelModel):
    guild_id: uuid.UUID
    name: str
    member_count: int


class RecommendedGuildList(_CamelModel):
    """추천 길드 응답 200: { items: [{ guildId, name, memberCount }] } [제안: 노션 명세에 없음]."""

    items: list[RecommendedGuildRead]


class AcquaintanceRead(_CamelModel):
    user_id: uuid.UUID
    nickname: str
    # GUILD_LEADER | GUILD_MEMBER
    relation: str


class AcquaintanceList(_CamelModel):
    """API-017 응답 200: { items: [{ userId, nickname, relation }] }."""

    items: list[AcquaintanceRead]


class GuildJoined(_CamelModel):
    """API-013 응답 200: { guildId }."""

    guild_id: uuid.UUID


class LeaderDelegate(_CamelModel):
    """API-016 요청: { userId } 새 길드장 (같은 길드원)."""

    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class LeaderDelegated(_CamelModel):
    """API-016 응답 200: { guildId, leaderUserId }."""

    guild_id: uuid.UUID
    leader_user_id: uuid.UUID


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    # 입력 오류(400)는 항목 목록(list), 그 밖의 에러는 객체이거나 null (app/core/errors.py)
    details: dict | list | None = None
