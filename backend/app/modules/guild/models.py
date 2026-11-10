"""길드 (Guild). 노션 'DB (1)' 4. GUILD.

소속은 USER.guild_id(0~1개)로, 길드장은 GUILD.leader_user_id로 나타낸다 (노션 DB ERD).
길드장이 그 길드 소속원이어야 한다는 제약은 서버 코드(service.py)에서 지킨다
(DB에서 걸지 코드에서 검사할지는 노션 DB '아직 정하지 못한 것' — 팀 확인 필요).
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 20


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 이름은 LLM·확인자 화면에 보내지 않는다 (노션 DB, backlog US-07 (권한))
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    leader_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
