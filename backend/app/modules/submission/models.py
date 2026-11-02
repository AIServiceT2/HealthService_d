"""운동 제출건 (WorkoutSubmission).

오늘(US-02 첫 기능)은 DATA-MODEL.md의 ★ 필드 중 계산에 필요한 것만 둔다.
user_id·권한은 로그인 방식이 미정이라 빼 둠 (first-feature.md 2절 #5).
"""

import uuid
from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.submission.constants import SubmissionStatus


class WorkoutSubmission(Base):
    __tablename__ = "workout_submission"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), default=SubmissionStatus.SUBMITTED)
    exercise_type: Mapped[str] = mapped_column(String(32))
    counted_reps: Mapped[int] = mapped_column(Integer)
    # PREPARED부터 채움. 오늘은 타격 수만 (first-feature.md 2절 #2는 팀 확인 필요)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
