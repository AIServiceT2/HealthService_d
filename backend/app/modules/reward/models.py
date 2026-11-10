"""지급 내역과 아이템. 노션 'DB (1)' 11. REWARD_LEDGER, 12. ITEM.

- REWARD_LEDGER의 키는 제출 ID라 한 제출건에 지급은 한 번만 생긴다 (멱등 키, backlog US-04).
- idempotency_key는 ERD에 없다 [추가·팀 확인 필요]. 노션 API-041의 Idempotency-Key로 같은 요청을
  다시 보냈는지(첫 결과 반환) 다른 요청인지(409 ALREADY_REWARDED) 가리려고 넣었다.
- 수치(경험치·피해)는 스냅샷에만 있고 지급 내역에는 시각만 둔다 (노션 DB '바꾼 것' 표).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ItemStatus(StrEnum):
    LOCKED = "LOCKED"
    # 잠금 해제 뒤 상태 이름은 노션 명세·DB 모두 미정 [제안·팀 확인 필요]
    UNLOCKED = "UNLOCKED"


class RewardLedger(Base):
    __tablename__ = "reward_ledger"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), primary_key=True
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column()
    # 보호 기간 끝 = rewarded_at + 24시간 (계산값이라 저장하지 않음)
    rewarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Item(Base):
    """얻은 아이템. 아이템 카탈로그가 미정이라 종류 칼럼은 아직 없다."""

    __tablename__ = "item"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_submission.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=ItemStatus.LOCKED)
