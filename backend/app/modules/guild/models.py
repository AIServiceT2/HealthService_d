"""길드 (Guild). 노션 'DB (1)' 4. GUILD.

소속은 USER.guild_id(0~1개)로, 길드장은 GUILD.leader_user_id로 나타낸다 (노션 DB ERD).
길드장이 그 길드 소속원이어야 한다는 제약은 서버 코드(service.py)에서 지킨다
(DB에서 걸지 코드에서 검사할지는 노션 DB '아직 정하지 못한 것' — 팀 확인 필요).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 20

# 초대 코드: 영문 대문자·숫자 6자 (노션 API-012 예시 "A7K2QX"). [제안·팀 확인 필요]
INVITE_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
INVITE_CODE_LENGTH = 6
INVITE_CODE_PATTERN = rf"^[A-Z0-9]{{{INVITE_CODE_LENGTH}}}$"
# 노션 API-012: expiresInHours는 선택, 기본값은 미정 → 명세 예시 72시간, 1시간~7일 [제안·팀 확인 필요]
INVITE_DEFAULT_HOURS = 72
INVITE_MIN_HOURS = 1
INVITE_MAX_HOURS = 168


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 이름은 LLM·확인자 화면에 보내지 않는다 (노션 DB, backlog US-07 (권한))
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    leader_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))


class GuildInvitation(Base):
    """길드 초대 코드. 노션 'DB (1)' 15. GUILD_INVITATION."""

    __tablename__ = "guild_invitation"

    code: Mapped[str] = mapped_column(String(INVITE_CODE_LENGTH), primary_key=True)
    guild_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
