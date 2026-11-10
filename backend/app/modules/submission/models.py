"""운동 제출건과 그에 딸린 기록. 노션 'DB (1)' 6. WORKOUT_SUBMISSION, 7. REP_EVENT, 9. DAILY_CAP_RESERVATION.

- idempotency_key는 ERD에 없다 [추가·팀 확인 필요]. 노션 API-026의 Idempotency-Key로 같은 요청을
  다시 보냈는지 가리려면 서버가 기억해야 해서 넣었다.
- snapshot(JSON)은 첫 기능(US-02)의 임시 칸이다. API-031에서 SUBMISSION_SNAPSHOT 테이블로 옮긴다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.submission.constants import SubmissionStatus


class WorkoutSubmission(Base):
    __tablename__ = "workout_submission"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    # 세션당 제출 1건 (노션 DB: session_id UNIQUE)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_session.id", ondelete="CASCADE"), unique=True
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column()
    # ERD는 EXERCISE_TYPE FK. 운동 종류가 코드 상수라 FK 없이 문자열 (workout_session/catalog.py)
    exercise_code: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default=SubmissionStatus.SUBMITTED)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # 서버가 다시 계산한 최종 인정량
    counted_reps: Mapped[int] = mapped_column(Integer)
    # 상태가 바뀔 때마다 1 증가 (If-Match 동시 수정 검사)
    version: Mapped[int] = mapped_column(Integer, default=0)
    # 0~1, 기준 미확정. 서버 재계산이 아직 없어 앱이 보낸 aiConfidence를 저장한다 (임시, service.py)
    confidence: Mapped[float] = mapped_column(Float)
    # AI_AUTO / REVIEWER. 승인 전에는 NULL (노션 API-028 예시)
    approval_path: Mapped[str | None] = mapped_column(String(16), default=None)
    ai_story: Mapped[str | None] = mapped_column(Text, default=None)
    ai_form_tip: Mapped[str | None] = mapped_column(Text, default=None)
    ai_summary: Mapped[str | None] = mapped_column(Text, default=None)
    ai_flags: Mapped[str | None] = mapped_column(Text, default=None)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)


class RepEvent(Base):
    """렙 기록. keypoints(렙의 관절 좌표 묶음)는 서버 재계산이 생기면 채운다 (지금은 NULL)."""

    __tablename__ = "rep_event"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), primary_key=True
    )
    rep_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    counted: Mapped[bool] = mapped_column(Boolean)
    keypoints: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)


class DailyCapReservation(Base):
    """일일 상한 예약. 날짜·운동 종류는 제출건의 started_at(KST)·exercise_code에서 구한다 (노션 DB 9절)."""

    __tablename__ = "daily_cap_reservation"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), primary_key=True
    )
    # 보상 대상 인정량
    amount: Mapped[int] = mapped_column(Integer)
    # 취소·반려 때 채운다. 해제된 예약은 합계에서 뺀다
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
