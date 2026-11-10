"""길드 주간 보스. 보스 모델은 노션 DB에 아직 없다 (명세: '보스 모델·체력·주 시작/마감은 미정') [가안·팀 확인 필요].

길드마다 한 주(월~일, KST)에 보스 1마리. 처음 조회할 때 만든다 (service.get_or_create_week_boss).
체력은 저장하지 않고 '최대 체력 − 피해 합계'로 계산한다 (battle/service.py).
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GuildBoss(Base):
    __tablename__ = "guild_boss"
    __table_args__ = (UniqueConstraint("guild_id", "week_start"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"), index=True)
    # 그 주 월요일 (KST)
    week_start: Mapped[date] = mapped_column(Date)
    hp_max: Mapped[int] = mapped_column(Integer)
