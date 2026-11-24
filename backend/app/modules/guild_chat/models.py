"""길드 채팅 메시지. 노션 DB GUILD_CHAT_MESSAGE (2026-11-24 저장소에서 추가, 기능명세 JN-040).

길드원이 쓴 TEXT와 서버가 만드는 알림(WORKOUT_DONE·BOSS_DEFEATED·BOSS_WEEK_STARTED)을 한 테이블에 두어
한 번에 시간순으로 조회한다. 삭제는 지우지 않고 숨긴다(deleted_at).
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 노션 API-073: 앞뒤 공백을 지운 뒤 1~300자 [제안]
BODY_MIN_LENGTH = 1
BODY_MAX_LENGTH = 300


class MessageType(StrEnum):
    TEXT = "TEXT"
    WORKOUT_DONE = "WORKOUT_DONE"
    BOSS_DEFEATED = "BOSS_DEFEATED"
    BOSS_WEEK_STARTED = "BOSS_WEEK_STARTED"


class GuildChatMessage(Base):
    __tablename__ = "guild_chat_message"
    __table_args__ = (
        # 같은 사람이 같은 clientMessageId로 다시 보내도 1개만 (API-073). 알림은 NULL이라 걸리지 않음
        UniqueConstraint("sender_user_id", "client_message_id"),
        # 최근 메시지 조회 (API-072)
        Index("ix_guild_chat_message_guild_created", "guild_id", "created_at", "id"),
        # 보스 알림은 길드·종류·주마다 1개 [제안: 보스 테이블이 ERD에 없어 payload의 weekStart로 구분]
        Index(
            "uq_guild_chat_message_boss_week",
            "guild_id",
            "type",
            text("(payload ->> 'weekStart')"),
            unique=True,
            postgresql_where=text("type IN ('BOSS_DEFEATED', 'BOSS_WEEK_STARTED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    # TEXT는 보낸 사람, WORKOUT_DONE은 운동한 길드원, BOSS_* 알림은 NULL
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    # TEXT일 때만 값이 있다
    body: Mapped[str | None] = mapped_column(String(BODY_MAX_LENGTH), default=None)
    # 알림 내용. WORKOUT_DONE {exerciseCode, hitCount, targetType}, BOSS_* {weekStart, hpMax}
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    # WORKOUT_DONE의 제출건. 제출건 1건에 알림 1개
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), unique=True, default=None
    )
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    # 트랜잭션 시작 시각(now())이 아니라 실제로 만든 시각 (같은 트랜잭션 안의 순서를 지키려고)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
