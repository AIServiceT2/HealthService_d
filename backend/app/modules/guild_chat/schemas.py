"""길드 채팅 API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

from app.modules.guild_chat.models import BODY_MAX_LENGTH, BODY_MIN_LENGTH

# 노션 API-073: 앞뒤 공백을 지운 뒤 1~300자 [제안]
MessageBody = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=BODY_MIN_LENGTH, max_length=BODY_MAX_LENGTH),
]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class MessageCreate(_CamelModel):
    """API-073 요청: { clientMessageId, body }. 텍스트만 보낼 수 있다 (type 등 다른 키는 400)."""

    model_config = ConfigDict(extra="forbid")

    client_message_id: uuid.UUID
    body: MessageBody


class MessageSender(_CamelModel):
    user_id: uuid.UUID
    nickname: str


class MessageRead(_CamelModel):
    """메시지 1개: { messageId, type, sender, body, payload, createdAt, deleted } (API-072·073, API-075 message)."""

    message_id: uuid.UUID
    type: str
    sender: MessageSender | None
    body: str | None
    payload: dict[str, Any] | None
    created_at: datetime
    deleted: bool

    @classmethod
    def from_view(cls, view) -> "MessageRead":
        """service.MessageView → 응답 모델 (서비스를 import하지 않으려고 속성만 읽는다)."""
        sender = view.sender
        return cls(
            message_id=view.message_id,
            type=view.type,
            sender=MessageSender(user_id=sender.user_id, nickname=sender.nickname) if sender else None,
            body=view.body,
            payload=view.payload,
            created_at=view.created_at,
            deleted=view.deleted,
        )


class MessageList(_CamelModel):
    """API-072 응답 200: { items, nextCursor, hasMoreAfter }. items는 오래된 것 → 최근 순."""

    items: list[MessageRead]
    next_cursor: str | None
    has_more_after: bool


class MessageDeleted(_CamelModel):
    """API-074 응답 200: { messageId, deleted: true, deletedBy }. deletedBy는 AUTHOR | LEADER."""

    message_id: uuid.UUID
    deleted: bool = True
    deleted_by: Literal["AUTHOR", "LEADER"]
