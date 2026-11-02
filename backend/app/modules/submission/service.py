"""제출건 규칙. 다른 모듈은 이 파일의 함수로만 제출건을 다룬다."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.submission.constants import HIT_UNIT, SubmissionStatus
from app.modules.submission.models import WorkoutSubmission


class SubmissionNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


class CalculationError(Exception):
    pass


def calculate_hit_count(exercise_type: str, counted_reps: int) -> int:
    """타격 수 = 인정량 ÷ 타격 단위(소수점 버림). 인정량 > 0이면 최소 1타, 0이면 0타 (03 R9)."""
    unit = HIT_UNIT.get(exercise_type)
    if unit is None:
        raise CalculationError(f"타격 단위가 없는 운동 종류: {exercise_type}")
    if counted_reps <= 0:
        return 0
    return max(1, counted_reps // unit)


def get_submission(db: Session, submission_id: uuid.UUID) -> WorkoutSubmission:
    submission = db.get(WorkoutSubmission, submission_id)
    if submission is None:
        raise SubmissionNotFound(str(submission_id))
    return submission


def prepare_submission(db: Session, submission_id: uuid.UUID) -> WorkoutSubmission:
    """SUBMITTED → PREPARED. 계산이 실패하면 아무것도 바꾸지 않고 SUBMITTED에 남긴다 (US-02 #1·#3)."""
    try:
        submission = db.scalars(
            select(WorkoutSubmission)
            .where(WorkoutSubmission.id == submission_id)
            .with_for_update()
        ).one_or_none()
        if submission is None:
            raise SubmissionNotFound(str(submission_id))
        if submission.status != SubmissionStatus.SUBMITTED:
            raise InvalidTransition(f"{submission.status} 상태는 계산할 수 없음")

        hit_count = calculate_hit_count(submission.exercise_type, submission.counted_reps)

        # 스냅샷 안 키 이름은 미정 (API.md 항목 1) — 팀 확인 필요
        submission.snapshot = {"hit_count": hit_count}
        submission.status = SubmissionStatus.PREPARED
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(submission)
    return submission
