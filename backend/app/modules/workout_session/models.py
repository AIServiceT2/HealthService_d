"""운동 세션 (WORKOUT_SESSION). 필드는 노션 ERD 13번 WORKOUT_SESSION을 따른다.

liveness_challenge_id·liveness_action·liveness_issued_at은 ERD에 없다 [추가·팀 확인 필요].
API-021에서 앱이 보낸 challengeId·동작이 세션 시작(API-020) 때 내려준 것과 같은지,
제한 시간 안인지 확인하려면 서버가 발급 내용을 기억해야 해서 넣었다.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SUBMITTED = "SUBMITTED"
    DISCARDED = "DISCARDED"


class WorkoutSession(Base):
    __tablename__ = "workout_session"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    # ERD는 EXERCISE_TYPE FK. 지금은 운동 종류를 코드 상수로 둬서 FK 없이 문자열 (catalog.py)
    exercise_code: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=SessionStatus.ACTIVE)
    goal_reps: Mapped[int | None] = mapped_column(Integer, default=None)
    goal_sets: Mapped[int | None] = mapped_column(Integer, default=None)
    # 공략 대상(DUNGEON / BOSS)과 데모 대상은 미정. 대상 테이블이 없어 FK 없음
    target_type: Mapped[str | None] = mapped_column(String(16), default=None)
    target_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    # 무작위 동작 확인 결과. 확인 전 NULL (API-021)
    liveness_passed: Mapped[bool | None] = mapped_column(default=None)
    liveness_challenge_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    liveness_action: Mapped[str] = mapped_column(String(32))
    liveness_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PoseChunk(Base):
    """관절 좌표 청크 (노션 ERD 14번 POSE_CHUNK). 같은 seq를 다시 보내면 덮어쓴다.

    원본 좌표의 보관·삭제 기간은 미정 (노션 ERD '아직 정하지 못한 것'). 세션 폐기(API-027) 때는 지운다.
    """

    __tablename__ = "pose_chunk"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_session.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    frames: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
