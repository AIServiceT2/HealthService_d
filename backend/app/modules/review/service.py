"""확인 요청·승인·반려 규칙 (노션 API-033~040, backlog US-03·07·08).

제출건 상태는 submission 모듈의 WorkoutSubmission에 있다. 상태를 바꿀 때는 제출건 행을 잠그고
version을 1 올린다 (취소 API-030과 같은 방식). 그래서 취소·승인·반려가 동시에 와도 하나만 성공한다.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.review import rules
from app.modules.submission import service as submission_service
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission


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
