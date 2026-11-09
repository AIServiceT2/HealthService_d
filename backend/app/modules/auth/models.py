"""사용자 (User). DATA-MODEL.md의 사용자 모델.

id·nickname·birth_date·guild_id는 DATA-MODEL.md 그대로이고,
provider·email·password_hash는 로그인에 필요해 더한 [추가] 필드다 (로그인 방식은 PRD 미정 —
노션 API-001 가안대로 EMAIL만 받는다). 'user'는 PostgreSQL 예약어라 테이블 이름은 app_user.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(16), default="EMAIL")
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(12))
    birth_date: Mapped[date] = mapped_column(Date)
    # 길드 테이블이 아직 없어 FK 없이 둔다 (길드 API 구현 때 연결)
    guild_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RefreshToken(Base):
    """refresh 토큰. 원문은 저장하지 않고 SHA-256 해시만 둔다. 폐기하면 revoked_at을 채운다."""

    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
