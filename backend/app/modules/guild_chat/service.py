"""길드 채팅 규칙 (기능명세 JN-040). 다른 모듈은 이 파일의 함수로만 채팅을 다룬다.

채팅은 운동 기록·인정량·보상·제출건 상태를 바꾸지 않는다. 메시지 내용은 LLM에 보내지 않는다.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.guild.models import Guild
from app.modules.guild_chat.models import GuildChatMessage, MessageType


class GuildNotFound(Exception):
    pass


class NotGuildMember(Exception):
    pass


class InvalidCursor(Exception):
    pass


class AfterMessageNotFound(Exception):
    """after에 넣은 메시지가 그 길드에 없다."""


@dataclass(frozen=True)
class Sender:
    user_id: uuid.UUID
    nickname: str


@dataclass(frozen=True)
class MessageView:
    """응답에 쓰는 메시지. 숨긴 메시지는 body·payload를 비운다 (노션 API-072)."""

    message_id: uuid.UUID
    type: str
    sender: Sender | None
    body: str | None
    payload: dict[str, Any] | None
    created_at: datetime
    deleted: bool


def _view(message: GuildChatMessage, sender: User | None) -> MessageView:
    deleted = message.deleted_at is not None
    return MessageView(
        message_id=message.id,
        type=message.type,
        sender=Sender(sender.id, sender.nickname) if sender is not None else None,
        body=None if deleted else message.body,
        payload=None if deleted else message.payload,
        created_at=message.created_at,
        deleted=deleted,
    )


def _require_member(db: Session, user_id: uuid.UUID, guild_id: uuid.UUID) -> User:
    """없는 길드면 GuildNotFound(404), 그 길드 소속원이 아니면 NotGuildMember(403)."""
    if db.get(Guild, guild_id) is None:
        raise GuildNotFound(str(guild_id))
    user = db.get(User, user_id)
    if user is None or user.guild_id != guild_id:
        raise NotGuildMember(str(user_id))
    return user


def _find_by_client_id(db: Session, user_id: uuid.UUID, client_message_id: uuid.UUID) -> GuildChatMessage | None:
    return db.scalars(
        select(GuildChatMessage).where(
            GuildChatMessage.sender_user_id == user_id,
            GuildChatMessage.client_message_id == client_message_id,
        )
    ).one_or_none()


def send_message(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, client_message_id: uuid.UUID, body: str
) -> tuple[MessageView, bool]:
    """길드원이 TEXT 메시지를 보낸다 (노션 API-073). (메시지, 새로 만들었는지)를 돌려준다.

    같은 사람이 같은 clientMessageId로 다시 보내면 새로 만들지 않고 처음 메시지를 돌려준다.
    두 요청이 동시에 와도 (sender_user_id, client_message_id) 유니크 제약으로 하나만 저장된다.
    """
    user = _require_member(db, user_id, guild_id)
    existing = _find_by_client_id(db, user_id, client_message_id)
    if existing is not None:
        return _view(existing, user), False

    message = GuildChatMessage(
        guild_id=guild_id,
        type=MessageType.TEXT,
        sender_user_id=user_id,
        body=body,
        client_message_id=client_message_id,
    )
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        # 같은 clientMessageId의 다른 요청이 먼저 저장했다
        db.rollback()
        existing = _find_by_client_id(db, user_id, client_message_id)
        if existing is None:
            raise
        return _view(existing, db.get(User, user_id)), False
    return _view(message, user), True


# ---- 메시지 목록 (노션 API-072) ----


@dataclass(frozen=True)
class MessagePage:
    # 오래된 것 → 최근 순
    items: list[MessageView]
    # 더 이전 메시지 페이지 커서. 없으면 None (after 조회에서는 항상 None)
    next_cursor: str | None
    # after 조회에서 limit보다 많이 남았는지
    has_more_after: bool


# 커서: 그 페이지에서 가장 오래된 메시지의 (created_at, id)를 base64url로 감싼 값.
# 클라이언트는 받은 값을 그대로 돌려보내기만 한다 (형식은 서버 내부 약속)
def _encode_cursor(message: GuildChatMessage) -> str:
    raw = f"{message.created_at.isoformat()}|{message.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at_text, id_text = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        at = datetime.fromisoformat(at_text)
        if at.tzinfo is None:
            raise ValueError(at_text)
        return at, uuid.UUID(id_text)
    except ValueError:
        raise InvalidCursor(cursor) from None


_ORDER_KEY = tuple_(GuildChatMessage.created_at, GuildChatMessage.id)


def list_messages(
    db: Session,
    user_id: uuid.UUID,
    guild_id: uuid.UUID,
    cursor: str | None,
    after: uuid.UUID | None,
    limit: int,
) -> MessagePage:
    """길드원만 메시지를 본다 (노션 API-072). 정렬은 (created_at, id).

    - 아무 값도 없으면 최근 limit개, cursor가 있으면 그보다 이전 limit개
    - after가 있으면 그 메시지 뒤에 온 것을 오래된 순으로 limit개 (재연결 뒤 빠진 메시지 채우기)
    - 숨긴 메시지도 자리는 남기고 body·payload만 비운다
    cursor와 after를 함께 쓰는 것은 라우터가 막는다.
    """
    _require_member(db, user_id, guild_id)
    query = (
        select(GuildChatMessage, User)
        .outerjoin(User, User.id == GuildChatMessage.sender_user_id)
        .where(GuildChatMessage.guild_id == guild_id)
    )

    if after is not None:
        anchor = db.get(GuildChatMessage, after)
        if anchor is None or anchor.guild_id != guild_id:
            raise AfterMessageNotFound(str(after))
        rows = db.execute(
            query.where(_ORDER_KEY > tuple_(anchor.created_at, anchor.id))
            .order_by(GuildChatMessage.created_at, GuildChatMessage.id)
            .limit(limit + 1)
        ).all()
        page = rows[:limit]
        return MessagePage([_view(m, u) for m, u in page], None, len(rows) > limit)

    if cursor is not None:
        query = query.where(_ORDER_KEY < tuple_(*_decode_cursor(cursor)))
    rows = db.execute(
        query.order_by(GuildChatMessage.created_at.desc(), GuildChatMessage.id.desc()).limit(limit + 1)
    ).all()
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1][0]) if len(rows) > limit else None
    return MessagePage([_view(m, u) for m, u in reversed(page)], next_cursor, False)
