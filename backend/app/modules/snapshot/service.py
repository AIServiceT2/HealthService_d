"""보상 스냅샷 규칙. 다른 모듈은 이 파일의 함수로만 스냅샷을 다룬다."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.snapshot import rules
from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.constants import HIT_UNIT, SubmissionStatus
from app.modules.submission.models import DailyCapReservation, WorkoutSubmission
from app.modules.workout_session.catalog import CATALOG_VERSION


class SubmissionNotFound(Exception):
    pass


class NotSubmitted(Exception):
    pass


class CalculationError(Exception):
    pass


class NotOwner(Exception):
    pass


class NoPreview(Exception):
    """스냅샷 없이 SUBMITTED도 아닌 건 (계산 전에 취소된 건 등)."""


def calculate_hit_count(exercise_code: str, rewardable_reps: int) -> int:
    """타격 수 = 보상 대상 인정량 ÷ 타격 단위(소수점 버림). 인정량 > 0이면 최소 1타, 0이면 0타 (03 R9)."""
    unit = HIT_UNIT.get(exercise_code)
    if unit is None:
        raise CalculationError(f"타격 단위가 없는 운동 종류: {exercise_code}")
    if rewardable_reps <= 0:
        return 0
    return max(1, rewardable_reps // unit)


def get_snapshot(db: Session, submission_id: uuid.UUID) -> SubmissionSnapshot | None:
    return db.get(SubmissionSnapshot, submission_id)


def prepare_snapshot(db: Session, submission_id: uuid.UUID) -> SubmissionSnapshot:
    """보상을 계산해 스냅샷을 고정하고 SUBMITTED → PREPARED로 바꾼다 (노션 API-031).

    - 이미 스냅샷이 있으면 그대로 돌려준다 (같은 요청을 다시 보내도 수치가 바뀌지 않음)
    - SUBMITTED가 아니면 NotSubmitted
    - 계산이 실패하면 아무것도 바꾸지 않고 SUBMITTED에 남는다 (US-02 #3)
    - 타격 수는 일일 상한 안에서 예약된 양(보상 대상)으로 센다. 상한 초과면 0타 (US-01·05)
    """
    try:
        submission = db.scalars(
            select(WorkoutSubmission).where(WorkoutSubmission.id == submission_id).with_for_update()
        ).one_or_none()
        if submission is None:
            raise SubmissionNotFound(str(submission_id))
        existing = db.get(SubmissionSnapshot, submission_id)
        if existing is not None:
            db.rollback()
            return existing
        if submission.status != SubmissionStatus.SUBMITTED:
            raise NotSubmitted(submission.status)

        reservation = db.get(DailyCapReservation, submission_id)
        rewardable = reservation.amount if reservation is not None else 0
        hit_count = calculate_hit_count(submission.exercise_code, rewardable)
        snapshot = SubmissionSnapshot(
            submission_id=submission_id,
            catalog_version=CATALOG_VERSION,
            hit_count=hit_count,
            exp=hit_count * rules.EXP_PER_HIT,
            total_damage=round(hit_count * rules.DAMAGE_PER_HIT * rules.DEFAULT_WEAKNESS_MULTIPLIER),
            weakness_multiplier=rules.DEFAULT_WEAKNESS_MULTIPLIER,
            drop_count=rules.DROP_COUNT_WHEN_HIT if hit_count > 0 else 0,
        )
        db.add(snapshot)
        submission.status = SubmissionStatus.PREPARED
        submission.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return snapshot


@dataclass(frozen=True)
class Preview:
    """API-032 미리보기. snapshot이 None이면 아직 계산 전(SUBMITTED)."""

    status: str
    snapshot: SubmissionSnapshot | None
    narrative_text: str | None


def get_reward_preview(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> Preview:
    """제출한 본인만 본다 (노션 API-032, backlog US-02 (권한)). 조회는 상태를 바꾸지 않는다.

    없으면 SubmissionNotFound, 남의 건이면 NotOwner, 스냅샷 없이 SUBMITTED도 아니면 NoPreview.
    """
    submission = db.get(WorkoutSubmission, submission_id)
    if submission is None:
        raise SubmissionNotFound(str(submission_id))
    if submission.user_id != user_id:
        raise NotOwner(str(user_id))
    snapshot = db.get(SubmissionSnapshot, submission_id)
    if snapshot is None and submission.status != SubmissionStatus.SUBMITTED:
        raise NoPreview(submission.status)
    return Preview(status=submission.status, snapshot=snapshot, narrative_text=submission.ai_story)
