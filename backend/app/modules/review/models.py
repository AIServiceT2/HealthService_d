"""확인 요청 (REVIEW_REQUEST). 노션 ERD 10번. 제출건당 최대 1건 (submission_id가 PK)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReviewRequest(Base):
    __tablename__ = "review_request"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), primary_key=True
    )
    # 확인자 1명. 신청자 본인은 안 됨 (backlog US-07 (실패·거절))
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # 반려 때만 채운다. 둘 다 필수 (backlog US-08). ERD는 REJECT_REASON FK지만 사유가 코드 상수라 FK 없음 (rules.py)
    reason_code: Mapped[str | None] = mapped_column(String(32), default=None)
    reason_text: Mapped[str | None] = mapped_column(Text, default=None)
