"""결과 카드 규칙 (노션 API-047). 상태를 바꾸지 않고 읽기만 한다."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reward.models import Item, RewardLedger
from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission import service as submission_service
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission

# LLM(L3·L4)이 없거나 실패했을 때 기본 문구. docs/DESIGN.md 5절 'LLM 결과 표시'의 제안 문구 그대로
# (서사 문구는 '지급 완료 화면에서만 사용'이라 REWARDED만 보여 주는 이 API에 맞음) [제안·팀 확인 필요]
FALLBACK_NARRATIVE = "운동 기록이 전투에 반영됐어요"
FALLBACK_FORM_COMMENT = "교정 안내를 불러오지 못했어요. 다음 운동 전 판정 기준을 확인해 주세요."

# 다른 모듈의 '없음·남의 건'을 그대로 쓴다
SubmissionNotFound = submission_service.SubmissionNotFound
NotOwner = submission_service.NotOwner


class NotRewarded(Exception):
    pass


@dataclass(frozen=True)
class Card:
    submission: WorkoutSubmission
    snapshot: SubmissionSnapshot
    drops: list[Item]
    rewarded_at: datetime

    @property
    def daily_cap_exceeded(self) -> bool:
        """일일 상한 초과로 타격 0이면 리플레이 없이 '일일 상한 초과' 카드 (backlog US-05)."""
        return self.snapshot.hit_count == 0


def get_rewarded(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> WorkoutSubmission:
    """본인 건이고 REWARDED여야 한다 (노션 API-047·048). 없음 404 → 남의 건 403 → 지급 전 409."""
    submission = submission_service.get_owned_submission(db, user_id, submission_id)
    if submission.status != SubmissionStatus.REWARDED:
        raise NotRewarded(submission.status)
    return submission


def get_card(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> Card:
    submission = get_rewarded(db, user_id, submission_id)
    snapshot = db.get(SubmissionSnapshot, submission_id)
    ledger = db.get(RewardLedger, submission_id)
    drops = list(db.scalars(select(Item).where(Item.submission_id == submission_id).order_by(Item.id)))
    return Card(submission=submission, snapshot=snapshot, drops=drops, rewarded_at=ledger.rewarded_at)
