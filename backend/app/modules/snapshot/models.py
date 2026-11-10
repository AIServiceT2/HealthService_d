"""보상 스냅샷. 노션 'DB (1)' 8. SUBMISSION_SNAPSHOT.

PREPARED가 될 때 한 번 만들고 바꾸지 않는다. 카탈로그가 바뀌거나 LLM을 다시 만들어도 이 값으로 지급한다.
"""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SubmissionSnapshot(Base):
    __tablename__ = "submission_snapshot"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), primary_key=True
    )
    catalog_version: Mapped[str] = mapped_column(String(32))
    hit_count: Mapped[int] = mapped_column(Integer)
    exp: Mapped[int] = mapped_column(Integer)
    total_damage: Mapped[int] = mapped_column(Integer)
    weakness_multiplier: Mapped[float] = mapped_column(Float)
    drop_count: Mapped[int] = mapped_column(Integer)
