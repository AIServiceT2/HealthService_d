"""확인 요청·승인·반려 규칙 (노션 API-033~040, backlog US-03·07·08).

제출건 상태는 submission 모듈의 WorkoutSubmission에 있다. 상태를 바꿀 때는 제출건 행을 잠그고
version을 1 올린다 (취소 API-030과 같은 방식). 그래서 취소·승인·반려가 동시에 와도 하나만 성공한다.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.guild import service as guild_service
from app.modules.review import rules
from app.modules.review.models import ReviewRequest
from app.modules.submission import service as submission_service
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import DailyCapReservation, WorkoutSubmission


class SubmissionNotFound(Exception):
    pass


class InvalidState(Exception):
    pass


class CanceledFirst(Exception):
    """취소가 먼저 처리된 건 (노션 API-033 412 CONCURRENT_UPDATE)."""


def _lock_submission(db: Session, submission_id: uuid.UUID) -> WorkoutSubmission:
    submission = db.scalars(
        select(WorkoutSubmission)
        .where(WorkoutSubmission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if submission is None:
        raise SubmissionNotFound(str(submission_id))
    return submission


def _liveness_passed(db: Session, submission: WorkoutSubmission) -> bool | None:
    return submission_service.details(db, [submission])[0].liveness_passed


def is_auto_approvable(confidence: float, liveness_passed: bool | None) -> bool:
    """확신도가 기준 이상이고 무작위 동작 확인을 통과했는가 (backlog US-03).

    확인 전(NULL)·실패(false)면 확신도와 관계없이 자동 승인하지 않는다.
    """
    return confidence >= rules.AUTO_APPROVAL_THRESHOLD and liveness_passed is True


# ---- 자동 승인 판정 (API-033) ----


@dataclass(frozen=True)
class AutoApprovalResult:
    decision: str
    submission: WorkoutSubmission
    liveness_passed: bool | None


def auto_approve(db: Session, submission_id: uuid.UUID) -> AutoApprovalResult:
    """PREPARED 건을 판정한다 (노션 API-033). 기준을 넘으면 APPROVED(AI_AUTO), 아니면 PREPARED 유지.

    - 취소된 건(CANCELED)이면 CanceledFirst (명세: 412 '취소가 먼저 처리되었습니다')
    - 그 밖에 PREPARED가 아니면 InvalidState (SUBMITTED → APPROVED 건너뛰기도 여기서 막힘, US-03)
    - 승인 여부는 확신도·무작위 동작 확인(규칙)만 보고 LLM 출력(ai_*)은 쓰지 않는다 (PRD 7절)
    """
    try:
        submission = _lock_submission(db, submission_id)
        if submission.status == SubmissionStatus.CANCELED:
            raise CanceledFirst(submission.status)
        if submission.status != SubmissionStatus.PREPARED:
            raise InvalidState(submission.status)

        liveness = _liveness_passed(db, submission)
        if is_auto_approvable(submission.confidence, liveness):
            submission.status = SubmissionStatus.APPROVED
            submission.approval_path = "AI_AUTO"
            submission.version += 1
            decision = "AUTO_APPROVED"
        else:
            decision = "NEEDS_REVIEW"
        db.commit()
    except Exception:
        db.rollback()
        raise
    return AutoApprovalResult(decision, submission, liveness)


# ---- 확인 요청 공유 내용 미리보기 (API-034) ----


class NotOwner(Exception):
    pass


@dataclass(frozen=True)
class ShareContent:
    """확인자에게 보낼 내용. 얼굴·나이·길드명은 넣지 않는다 (backlog US-07 (권한)).

    관절 선 리플레이(skeleton_replay_url)·L1·L2는 아직 만드는 기능이 없어 빈 값이다.
    통증 안내 고정 문구는 미정 (노션 API-034).
    """

    skeleton_replay_url: str | None
    summary: str | None
    anomalies: list[dict]
    pain_notice: str | None


def _share_content(submission: WorkoutSubmission) -> ShareContent:
    return ShareContent(
        skeleton_replay_url=None, summary=submission.ai_summary, anomalies=[], pain_notice=None
    )


def _check_reviewable(db: Session, submission: WorkoutSubmission) -> None:
    """확인 요청을 보낼 수 있는 건인가: PREPARED이고 자동 승인 대상이 아님 (backlog US-03·07).

    자동 승인 대상(확신도 기준 이상 + 무작위 동작 통과)은 사람 확인 없이 승인되므로 확인 요청을 막는다.
    """
    if submission.status != SubmissionStatus.PREPARED:
        raise InvalidState(submission.status)
    if is_auto_approvable(submission.confidence, _liveness_passed(db, submission)):
        raise InvalidState("AUTO_APPROVABLE")


def share_preview(db: Session, user_id: uuid.UUID, submission_id: uuid.UUID) -> ShareContent:
    """신청자가 확인자에게 보낼 내용을 먼저 본다 (노션 API-034, backlog US-07 (정상) 2번째)."""
    try:
        submission = submission_service.get_owned_submission(db, user_id, submission_id)
    except submission_service.SubmissionNotFound:
        raise SubmissionNotFound(str(submission_id)) from None
    except submission_service.NotOwner:
        raise NotOwner(str(user_id)) from None
    _check_reviewable(db, submission)
    return _share_content(submission)


# ---- 확인 요청 (API-035) ----


class InvalidRequest(Exception):
    """본인을 지정했거나 미리보기를 확인하지 않음 (400)."""


class VersionMismatch(Exception):
    pass


class NotAllowedReviewer(Exception):
    """지인이나 길드장이 아닌 사람 (403)."""


def allowed_reviewers(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """확인자로 고를 수 있는 사람. 지금은 '내 길드의 길드장'뿐이다 [가정·팀 확인 필요].

    "지인"을 어떻게 정할지(친구 목록 등)는 미정이라 아직 넣지 않았다 (PRD 미정 표, backlog US-07 미확정).
    길드가 없거나 본인이 길드장이면 고를 사람이 없다.
    """
    user = db.get(User, user_id)
    if user is None or user.guild_id is None:
        return set()
    leader = guild_service.get_guild_info(db, user_id, user.guild_id).leader_user_id
    return {leader} - {user_id}


@dataclass(frozen=True)
class RequestResult:
    submission: WorkoutSubmission
    review: ReviewRequest
    reviewer: User


def request_review(
    db: Session,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    share_preview_confirmed: bool,
    expected_version: int,
) -> RequestResult:
    """PREPARED → PENDING_REVIEW, 확인 요청 1건을 만든다 (노션 API-035, backlog US-07).

    검사 순서: 입력 400 → 없음 404 → 남의 건 403 → version 412 → 상태·이미 요청함 409 → 확인자 자격 403.
    """
    if not share_preview_confirmed:
        raise InvalidRequest("SHARE_PREVIEW_NOT_CONFIRMED")
    if reviewer_user_id == user_id:
        raise InvalidRequest("SELF_REVIEWER")
    try:
        submission = _lock_submission(db, submission_id)
        if submission.user_id != user_id:
            raise NotOwner(str(user_id))
        if submission.version != expected_version:
            raise VersionMismatch(submission.version)
        if db.get(ReviewRequest, submission_id) is not None:
            raise InvalidState("ALREADY_REQUESTED")
        _check_reviewable(db, submission)
        if reviewer_user_id not in allowed_reviewers(db, user_id):
            raise NotAllowedReviewer(str(reviewer_user_id))

        review = ReviewRequest(
            submission_id=submission_id,
            reviewer_user_id=reviewer_user_id,
            requested_at=datetime.now(UTC),
        )
        db.add(review)
        submission.status = SubmissionStatus.PENDING_REVIEW
        submission.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RequestResult(submission, review, db.get(User, reviewer_user_id))


# ---- 받은 확인 요청 목록 (API-036) ----


class InvalidCursor(Exception):
    pass


@dataclass(frozen=True)
class ReceivedItem:
    review: ReviewRequest
    submission: WorkoutSubmission
    requester: User


@dataclass(frozen=True)
class ReceivedPage:
    items: list[ReceivedItem]
    next_cursor: str | None


# 커서: 마지막 항목의 (requested_at, submission_id)를 base64url로 감싼 값 (제출 목록 API-029와 같은 방식)
def _encode_cursor(review: ReviewRequest) -> str:
    raw = f"{review.requested_at.isoformat()}|{review.submission_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at_text, id_text = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        at = datetime.fromisoformat(at_text)
        if at.tzinfo is None:
            raise ValueError(at_text)
        return at, uuid.UUID(id_text)
    except ValueError:
        raise InvalidCursor(cursor) from None


def list_received(
    db: Session, reviewer_id: uuid.UUID, *, pending_only: bool, cursor: str | None, limit: int
) -> ReceivedPage:
    """나에게 온 확인 요청만, 최신순 (노션 API-036). 요청받지 않은 건은 보이지 않는다 (US-07 (권한)).

    pending_only=True면 아직 처리하지 않은(PENDING_REVIEW) 건만. 정렬은 명세에 없어 최신순으로 정함 [제안].
    """
    query = (
        select(ReviewRequest, WorkoutSubmission, User)
        .join(WorkoutSubmission, WorkoutSubmission.id == ReviewRequest.submission_id)
        .join(User, User.id == WorkoutSubmission.user_id)
        .where(ReviewRequest.reviewer_user_id == reviewer_id)
    )
    if pending_only:
        query = query.where(WorkoutSubmission.status == SubmissionStatus.PENDING_REVIEW)
    if cursor is not None:
        after_at, after_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(ReviewRequest.requested_at, ReviewRequest.submission_id) < tuple_(after_at, after_id)
        )
    rows = db.execute(
        query.order_by(ReviewRequest.requested_at.desc(), ReviewRequest.submission_id.desc()).limit(
            limit + 1
        )
    ).all()
    page, more = rows[:limit], len(rows) > limit
    items = [ReceivedItem(r, s, u) for r, s, u in page]
    return ReceivedPage(items, _encode_cursor(items[-1].review) if more else None)


# ---- 확인 자료 열람 (API-037) ----


class ReviewNotFound(Exception):
    pass


class NotReviewer(Exception):
    pass


@dataclass(frozen=True)
class Material:
    submission: WorkoutSubmission
    requester: User
    content: ShareContent


def _assigned_review(db: Session, reviewer_id: uuid.UUID, submission_id: uuid.UUID) -> ReviewRequest:
    """확인 요청이 없으면 ReviewNotFound, 요청받은 확인자가 아니면 NotReviewer."""
    review = db.get(ReviewRequest, submission_id)
    if review is None:
        raise ReviewNotFound(str(submission_id))
    if review.reviewer_user_id != reviewer_id:
        raise NotReviewer(str(reviewer_id))
    return review


def review_material(db: Session, reviewer_id: uuid.UUID, submission_id: uuid.UUID) -> Material:
    """요청받은 확인자만 확인 자료를 본다 (노션 API-037, backlog US-07 (권한)).

    처리한 뒤(승인·반려·취소)에도 같은 자료를 볼 수 있다. ai_summary·ai_flags는 표시만 하고
    상태를 바꾸지 않는다 (US-07 (LLM)).
    """
    _assigned_review(db, reviewer_id, submission_id)
    submission = db.get(WorkoutSubmission, submission_id)
    return Material(submission, db.get(User, submission.user_id), _share_content(submission))


# ---- 확인자 승인 (API-038) ----


def _lock_for_reviewer(
    db: Session, reviewer_id: uuid.UUID, submission_id: uuid.UUID, expected_version: int
) -> tuple[WorkoutSubmission, ReviewRequest]:
    """제출건 행을 잠근 뒤 확인자·version·상태를 검사한다 (승인·반려 공통).

    검사 순서: 확인 요청 없음 404 → 요청받은 확인자 아님 403 → version 412 → PENDING_REVIEW 아님 409.
    신청자 본인은 확인자가 될 수 없으므로(API-035) 403에서 막힌다.
    """
    try:
        submission = _lock_submission(db, submission_id)
    except SubmissionNotFound:
        raise ReviewNotFound(str(submission_id)) from None
    review = _assigned_review(db, reviewer_id, submission_id)
    if submission.version != expected_version:
        raise VersionMismatch(submission.version)
    if submission.status != SubmissionStatus.PENDING_REVIEW:
        raise InvalidState(submission.status)
    return submission, review


def approve_review(
    db: Session, reviewer_id: uuid.UUID, submission_id: uuid.UUID, expected_version: int
) -> WorkoutSubmission:
    """PENDING_REVIEW → APPROVED(REVIEWER) (노션 API-038, backlog US-07).

    취소(API-030)와 같은 행을 잠그고 version을 비교하므로 동시에 와도 하나만 성공한다.
    """
    try:
        submission, _ = _lock_for_reviewer(db, reviewer_id, submission_id, expected_version)
        submission.status = SubmissionStatus.APPROVED
        submission.approval_path = "REVIEWER"
        submission.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return submission


# ---- 확인자 반려 (API-039) ----


@dataclass(frozen=True)
class RejectResult:
    submission: WorkoutSubmission
    released_reps: int


def reject_review(
    db: Session,
    reviewer_id: uuid.UUID,
    submission_id: uuid.UUID,
    expected_version: int,
    reason_code: str,
    reason_text: str,
) -> RejectResult:
    """PENDING_REVIEW → REJECTED → CLOSED, 상한 예약을 해제한다 (노션 API-039, backlog US-08).

    - 사유 코드·설명은 둘 다 있어야 한다 (라우터에서 검사, US-08 (실패·거절))
    - 카메라 세션 건은 재제출할 수 없어 REJECTED를 거쳐 바로 CLOSED (03 3-2). MVP 제출건은 모두 카메라 세션
    - 상태가 두 번 바뀌므로 version도 2 오른다 (노션 예시 4 → 6)
    - 반려는 확인자의 요청으로만 일어난다. AI 판정·ai_flags로 반려하는 경로는 없다 (US-08)
    """
    try:
        submission, review = _lock_for_reviewer(db, reviewer_id, submission_id, expected_version)
        review.reason_code = reason_code
        review.reason_text = reason_text

        reservation = db.get(DailyCapReservation, submission_id)
        released = 0
        if reservation is not None and reservation.released_at is None:
            reservation.released_at = datetime.now(UTC)
            released = reservation.amount

        submission.status = SubmissionStatus.REJECTED
        submission.version += 1
        db.flush()
        submission.status = SubmissionStatus.CLOSED
        submission.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RejectResult(submission, released)
