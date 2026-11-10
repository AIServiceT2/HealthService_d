"""제출건 규칙. 다른 모듈은 이 파일의 함수로만 제출건을 다룬다."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.submission.constants import BLOCKING_STATUSES, HIT_UNIT, SubmissionStatus
from app.modules.submission.models import DailyCapReservation, RepEvent, WorkoutSubmission
from app.modules.workout_session import service as session_service
from app.modules.workout_session.catalog import EXERCISES
from app.modules.workout_session.models import SessionStatus


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

        hit_count = calculate_hit_count(submission.exercise_code, submission.counted_reps)

        # 스냅샷 안 키 이름은 미정 (API.md 항목 1) — 팀 확인 필요
        submission.snapshot = {"hit_count": hit_count}
        submission.status = SubmissionStatus.PREPARED
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(submission)
    return submission


# ---- 일일 상한 예약 (노션 DB 9절) ----


def _kst_day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=session_service.KST)
    return start, start + timedelta(days=1)


def reserved_amount(db: Session, user_id: uuid.UUID, exercise_code: str, day: date) -> int:
    """그날(KST, 제출건 started_at 기준) 해제되지 않은 상한 예약 합계."""
    start, end = _kst_day_range(day)
    total = db.scalar(
        select(func.coalesce(func.sum(DailyCapReservation.amount), 0))
        .join(WorkoutSubmission, WorkoutSubmission.id == DailyCapReservation.submission_id)
        .where(
            WorkoutSubmission.user_id == user_id,
            WorkoutSubmission.exercise_code == exercise_code,
            WorkoutSubmission.started_at >= start,
            WorkoutSubmission.started_at < end,
            DailyCapReservation.released_at.is_(None),
        )
    )
    return int(total)


# ---- 세션 종료·운동 제출 (노션 API-026) ----


@dataclass(frozen=True)
class RepIn:
    rep_no: int
    ts: datetime
    counted: bool


@dataclass(frozen=True)
class SubmitResult:
    submission: WorkoutSubmission
    reserved_reps: int


def recount_reps(reps: Sequence[RepIn]) -> int:
    """서버 재계산 인정량. [임시] ai/ 엔진(/internal/recount) 연결 전이라 앱이 보낸 렙 중
    counted=true인 수를 쓴다. 연결하려면 세션에 fps·화면 크기·좌우 반전·모델 버전을 저장하고
    청크 형식(kp [x,y,v])을 엔진 형식(landmarks)으로 바꿔야 한다 (팀 확인 필요).
    """
    return sum(1 for rep in reps if rep.counted)


def _validation_failed(reason: str, **details) -> AppError:
    return AppError(
        400, "VALIDATION_FAILED", "누락된 청크가 있거나 입력값이 올바르지 않습니다.",
        {"reason": reason, **details},
    )


def _replay(db: Session, user_id: uuid.UUID, session_id: uuid.UUID, key: uuid.UUID) -> SubmitResult:
    """이미 제출된 세션. 같은 Idempotency-Key면 첫 결과를, 다르면 409."""
    submission = db.scalars(
        select(WorkoutSubmission).where(WorkoutSubmission.session_id == session_id)
    ).one()
    if submission.user_id != user_id or submission.idempotency_key != key:
        raise AppError(409, "INVALID_STATE", "이미 제출했거나 폐기된 세션입니다.")
    reservation = db.get(DailyCapReservation, submission.id)
    return SubmitResult(submission, reservation.amount if reservation else 0)


def submit_session(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    idempotency_key: uuid.UUID,
    total_chunks: int,
    ended_at: datetime,
    client_rep_count: int,
    reps: Sequence[RepIn],
    ai_confidence: float,
) -> SubmitResult:
    """세션을 끝내고 제출건(SUBMITTED)을 만든다 (노션 API-026).

    - 청크 1..totalChunks가 모두 있어야 한다 (없으면 400, details.missingSeq)
    - 서버 재계산 값보다 앱 렙 수가 크면 422 SERVER_RECOUNT_MISMATCH
    - 같은 사용자·운동의 활성 제출건과 시간이 겹치면 409 DUPLICATE_SUBMISSION
    - 그날 남은 상한만큼 원자적으로 예약한다. 다 찼으면 제출건은 만들고 예약 0
    """
    try:
        # 같은 사용자의 제출을 하나씩 처리해 상한 예약이 겹치지 않게 한다 (사용자 → 세션 순서로 잠금)
        db.scalars(select(User).where(User.id == user_id).with_for_update()).one()
        session = session_service.get_owned_session(db, user_id, session_id, lock=True)
        if session.status == SessionStatus.SUBMITTED:
            result = _replay(db, user_id, session_id, idempotency_key)
            db.rollback()
            return result
        if session.status == SessionStatus.DISCARDED:
            raise AppError(409, "INVALID_STATE", "이미 제출했거나 폐기된 세션입니다.")

        if ended_at <= session.started_at:
            raise _validation_failed("ENDED_BEFORE_START")
        rep_nos = [rep.rep_no for rep in reps]
        if len(set(rep_nos)) != len(rep_nos):
            raise _validation_failed("DUPLICATE_REP_NO")
        received = set(session_service.received_seqs(db, session_id))
        missing = [seq for seq in range(1, total_chunks + 1) if seq not in received]
        if missing:
            raise _validation_failed("MISSING_CHUNKS", missingSeq=missing)
        extra = sorted(seq for seq in received if seq > total_chunks)
        if extra:
            raise _validation_failed("UNEXPECTED_CHUNKS", extraSeq=extra)

        counted_reps = recount_reps(reps)
        if client_rep_count > counted_reps:
            raise AppError(
                422, "SERVER_RECOUNT_MISMATCH", "인정 렙 수가 서버 재계산 값보다 큽니다.",
                {"clientRepCount": client_rep_count, "serverRepCount": counted_reps},
            )

        overlapping = db.scalar(
            select(func.count())
            .select_from(WorkoutSubmission)
            .where(
                WorkoutSubmission.user_id == user_id,
                WorkoutSubmission.exercise_code == session.exercise_code,
                WorkoutSubmission.status.in_(BLOCKING_STATUSES),
                WorkoutSubmission.started_at < ended_at,
                WorkoutSubmission.ended_at > session.started_at,
            )
        )
        if overlapping:
            raise AppError(409, "DUPLICATE_SUBMISSION", "같은 시간대에 활성 제출건이 있습니다.")

        day = session.started_at.astimezone(session_service.KST).date()
        cap = EXERCISES[session.exercise_code].daily_cap
        remaining = max(cap - reserved_amount(db, user_id, session.exercise_code, day), 0)
        # 상한을 일부만 남겼을 때 남은 만큼만 예약한다 [가정 — 노션 DB '부분 예약' 미정]
        reserved = min(counted_reps, remaining)

        submission = WorkoutSubmission(
            user_id=user_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            exercise_code=session.exercise_code,
            status=SubmissionStatus.SUBMITTED,
            started_at=session.started_at,
            ended_at=ended_at,
            counted_reps=counted_reps,
            version=0,
            confidence=ai_confidence,
        )
        db.add(submission)
        db.flush()
        db.add_all(
            RepEvent(submission_id=submission.id, rep_no=r.rep_no, ts=r.ts, counted=r.counted)
            for r in reps
        )
        db.add(DailyCapReservation(submission_id=submission.id, amount=reserved))
        session.status = SessionStatus.SUBMITTED
        db.commit()
    except Exception:
        db.rollback()
        raise
    return SubmitResult(submission, reserved)


def submission_for_session(db: Session, session_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(WorkoutSubmission.id).where(WorkoutSubmission.session_id == session_id))
