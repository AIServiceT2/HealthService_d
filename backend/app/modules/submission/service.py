"""제출건 규칙. 다른 모듈은 이 파일의 함수로만 제출건을 다룬다."""

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.submission.constants import (
    BLOCKING_STATUSES,
    CANCELABLE_STATUSES,
    SubmissionStatus,
)
from app.modules.submission.models import DailyCapReservation, RepEvent, WorkoutSubmission
from app.modules.workout_session import service as session_service
from app.modules.workout_session.catalog import EXERCISES
from app.modules.workout_session.models import SessionStatus, WorkoutSession


class SubmissionNotFound(Exception):
    pass


class NotOwner(Exception):
    pass


@dataclass(frozen=True)
class SubmissionDetail:
    """API-028 제출 상태 조회 결과 (API-029 목록 항목도 같은 형식)."""

    submission: WorkoutSubmission
    reserved_reps: int
    liveness_passed: bool | None


def get_owned_submission(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> WorkoutSubmission:
    """없으면 SubmissionNotFound, 남의 건이면 NotOwner (노션 API-028 Error Code)."""
    submission = db.get(WorkoutSubmission, submission_id)
    if submission is None:
        raise SubmissionNotFound(str(submission_id))
    if submission.user_id != user_id:
        raise NotOwner(str(user_id))
    return submission


def details(db: Session, submissions: Sequence[WorkoutSubmission]) -> list[SubmissionDetail]:
    """예약량·무작위 동작 확인 결과를 붙인다. reservedReps는 해제되지 않은 예약만 센다
    (취소·반려로 해제되면 0) [제안·팀 확인 필요]."""
    ids = [s.id for s in submissions]
    if not ids:
        return []
    reserved = {
        r.submission_id: (r.amount if r.released_at is None else 0)
        for r in db.scalars(select(DailyCapReservation).where(DailyCapReservation.submission_id.in_(ids)))
    }
    liveness = dict(
        db.execute(
            select(WorkoutSession.id, WorkoutSession.liveness_passed).where(
                WorkoutSession.id.in_([s.session_id for s in submissions])
            )
        ).all()
    )
    return [
        SubmissionDetail(s, reserved.get(s.id, 0), liveness.get(s.session_id)) for s in submissions
    ]


def get_submission_detail(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> SubmissionDetail:
    return details(db, [get_owned_submission(db, user_id, submission_id)])[0]


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


# ---- 내 제출 목록 (노션 API-029) ----


class InvalidCursor(Exception):
    pass


@dataclass(frozen=True)
class SubmissionPage:
    items: list[SubmissionDetail]
    next_cursor: str | None


# 커서: 마지막 항목의 (started_at, id)를 base64url로 감싼 값. 클라이언트는 받은 값을 그대로 돌려보낸다
def _encode_cursor(submission: WorkoutSubmission) -> str:
    raw = f"{submission.started_at.isoformat()}|{submission.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        started_text, id_text = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        started_at = datetime.fromisoformat(started_text)
        if started_at.tzinfo is None:
            raise ValueError(started_text)
        return started_at, uuid.UUID(id_text)
    except ValueError:
        raise InvalidCursor(cursor) from None


def list_my_submissions(
    db: Session,
    user_id: uuid.UUID,
    *,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    cursor: str | None,
    limit: int,
) -> SubmissionPage:
    """본인 제출건만, 최신순(started_at 내림차순, 같으면 id)으로 (노션 API-029).

    from·to는 KST 날짜이고 둘 다 포함한다. 정렬은 명세에 없어 최신순으로 정함 [제안].
    """
    query = select(WorkoutSubmission).where(WorkoutSubmission.user_id == user_id)
    if status is not None:
        query = query.where(WorkoutSubmission.status == status)
    if date_from is not None:
        query = query.where(WorkoutSubmission.started_at >= _kst_day_range(date_from)[0])
    if date_to is not None:
        query = query.where(WorkoutSubmission.started_at < _kst_day_range(date_to)[1])
    if cursor is not None:
        after_started, after_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(WorkoutSubmission.started_at, WorkoutSubmission.id) < tuple_(after_started, after_id)
        )
    rows = list(
        db.scalars(
            query.order_by(WorkoutSubmission.started_at.desc(), WorkoutSubmission.id.desc()).limit(limit + 1)
        )
    )
    page, more = rows[:limit], len(rows) > limit
    return SubmissionPage(details(db, page), _encode_cursor(page[-1]) if more else None)


# ---- 승인 전 제출 취소 (노션 API-030) ----


class VersionMismatch(Exception):
    pass


class NotCancelable(Exception):
    pass


@dataclass(frozen=True)
class CancelResult:
    submission: WorkoutSubmission
    released_reps: int


def cancel_submission(
    db: Session, user_id: uuid.UUID, submission_id: uuid.UUID, expected_version: int
) -> CancelResult:
    """신청자 본인이 승인 전 제출건을 취소하고 상한 예약을 해제한다 (노션 API-030, backlog US-06).

    행을 잠근 채 version을 비교하므로 승인·다른 취소와 동시에 와도 하나만 성공한다.
    검사 순서: 없음 404 → 남의 건 403 → version 불일치 412 → 취소할 수 없는 상태 409.
    """
    try:
        submission = db.scalars(
            select(WorkoutSubmission)
            .where(WorkoutSubmission.id == submission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one_or_none()
        if submission is None:
            raise SubmissionNotFound(str(submission_id))
        if submission.user_id != user_id:
            raise NotOwner(str(user_id))
        if submission.version != expected_version:
            raise VersionMismatch(submission.version)
        if submission.status not in CANCELABLE_STATUSES:
            raise NotCancelable(submission.status)

        reservation = db.get(DailyCapReservation, submission_id)
        released = 0
        if reservation is not None and reservation.released_at is None:
            reservation.released_at = datetime.now(UTC)
            released = reservation.amount
        submission.status = SubmissionStatus.CANCELED
        submission.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return CancelResult(submission, released)
