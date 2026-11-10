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
from app.modules.submission.models import RepEvent, WorkoutSubmission

# LLM(L3·L4)이 없거나 실패했을 때 기본 문구. docs/DESIGN.md 5절 'LLM 결과 표시'의 제안 문구 그대로
# (서사 문구는 '지급 완료 화면에서만 사용'이라 REWARDED만 보여 주는 이 API에 맞음) [제안·팀 확인 필요]
FALLBACK_NARRATIVE = "운동 기록이 전투에 반영됐어요"
FALLBACK_FORM_COMMENT = "교정 안내를 불러오지 못했어요. 다음 운동 전 판정 기준을 확인해 주세요."

# 다른 모듈의 '없음·남의 건'을 그대로 쓴다
SubmissionNotFound = submission_service.SubmissionNotFound
NotOwner = submission_service.NotOwner


class NotRewarded(Exception):
    pass


class DailyCapExceeded(Exception):
    """타격 0 (일일 상한 초과) → 리플레이 없이 '일일 상한 초과' 카드 (backlog US-05)."""


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


# ---- 전투 리플레이 (노션 API-048) ----

# 리플레이는 30초를 넘지 않는다 (노션 API-048, backlog US-05)
REPLAY_MAX_SECONDS = 30.0
HIT = "HIT"
MISS = "MISS"
# 인정됐지만 그날 상한을 넘어 타격이 되지 않은 렙 [제안·팀 확인 필요]
MISS_DAILY_CAP = "DAILY_CAP"


@dataclass(frozen=True)
class ReplayEvent:
    rep_index: int
    t: float
    type: str
    damage: int | None
    reason: str | None


@dataclass(frozen=True)
class Replay:
    hit_count: int
    events: list[ReplayEvent]


def _playback_times(started_at: datetime, reps: list[RepEvent]) -> list[float]:
    """세션 시작부터 지난 초. 가장 늦은 렙이 30초를 넘으면 간격 비율을 유지한 채 30초 안으로 줄인다 [제안]."""
    offsets = [max((rep.ts - started_at).total_seconds(), 0.0) for rep in reps]
    longest = max(offsets, default=0.0)
    scale = REPLAY_MAX_SECONDS / longest if longest > REPLAY_MAX_SECONDS else 1.0
    return [round(offset * scale, 1) for offset in offsets]


def get_replay(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> Replay:
    """본인의 REWARDED 건 리플레이 (노션 API-048). 타격 0이면 DailyCapExceeded.

    - 인정 렙 중 앞에서부터 타격 수만큼 HIT (콤보 수 = 결과 카드 타격 수, US-05)
    - 인정됐지만 상한을 넘은 렙은 MISS(DAILY_CAP), 인정되지 않은 렙은 MISS (사유는 저장되지 않아 null)
    - HIT 피해는 스냅샷 총 피해를 타격 수로 나누고 나머지는 마지막 타격에 더해, 합이 총 피해와 같다
    """
    submission = get_rewarded(db, user_id, submission_id)
    snapshot = db.get(SubmissionSnapshot, submission_id)
    if snapshot.hit_count == 0:
        raise DailyCapExceeded(str(submission_id))
    reps = list(db.scalars(select(RepEvent).where(RepEvent.submission_id == submission_id).order_by(RepEvent.rep_no)))
    times = _playback_times(submission.started_at, reps)

    per_hit, remainder = divmod(snapshot.total_damage, snapshot.hit_count)
    events, hits = [], 0
    for rep, t in zip(reps, times, strict=True):
        if rep.counted and hits < snapshot.hit_count:
            hits += 1
            damage = per_hit + (remainder if hits == snapshot.hit_count else 0)
            events.append(ReplayEvent(rep.rep_no, t, HIT, damage, None))
        else:
            reason = MISS_DAILY_CAP if rep.counted else None
            events.append(ReplayEvent(rep.rep_no, t, MISS, None, reason))
    return Replay(hit_count=snapshot.hit_count, events=events)
