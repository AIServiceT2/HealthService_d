"""review API. 노션 '전운시 API 명세서' API-033~040 (backlog US-03·07·08).

로그인 확인은 auth 모듈의 get_current_user (Bearer access token).
/internal 경로는 snapshot 모듈의 require_internal_token(X-Internal-Token)을 같이 쓴다.
"""

import re
import uuid

from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.review import rules, service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.review.schemas import (
    Anomaly,
    AutoApprovalResponse,
    ErrorResponse,
    ReceivedReviewItem,
    ReceivedReviewList,
    RequesterNickname,
    RequesterRead,
    ReviewMaterial,
    ReviewApproved,
    ReviewerRead,
    ReviewRequestCreate,
    ReviewRequestCreated,
    SharePreviewResponse,
)
from app.modules.snapshot.internal import require_internal_token

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["review"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)


def _not_found() -> AppError:
    return AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")


def _validation_failed(reason: str) -> AppError:
    return AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": reason})


def _concurrent_update(current_version: int) -> AppError:
    return AppError(
        412, "CONCURRENT_UPDATE", "다른 요청이 먼저 처리되었습니다.", {"currentVersion": current_version}
    )


# If-Match 값: "3" 또는 3 (약한 ETag W/"3"도 받음). 취소(API-030, submission/router.py)와 같은 형식
_IF_MATCH = re.compile(r'^(?:W/)?"?(\d+)"?$')


def _parse_if_match(value: str) -> int:
    match = _IF_MATCH.fullmatch(value.strip())
    if match is None:
        raise _validation_failed("INVALID_IF_MATCH")
    return int(match.group(1))


@router.post(
    "/internal/submissions/{id}/auto-approval",
    summary="[API-033] 자동 승인 판정",
    description=(
        "권한: SYSTEM (서버 내부 호출 전용, X-Internal-Token). 확신도가 기준(0.90, 미확정) 이상이고 "
        "무작위 동작 확인을 통과한 PREPARED 건만 APPROVED(AI_AUTO). 미달이면 PREPARED에 남고 NEEDS_REVIEW. "
        "PREPARED가 아니면 409 INVALID_STATE, 취소가 먼저 처리됐으면 412 CONCURRENT_UPDATE"
    ),
    response_model=AutoApprovalResponse,
    dependencies=[Depends(require_internal_token)],
)
def api_033(id: uuid.UUID, db: Session = Depends(get_db)) -> AutoApprovalResponse:
    try:
        result = service.auto_approve(db, id)
    except service.SubmissionNotFound:
        raise _not_found()
    except service.CanceledFirst:
        raise AppError(412, "CONCURRENT_UPDATE", "취소가 먼저 처리되었습니다.")
    except service.InvalidState:
        raise AppError(409, "INVALID_STATE", "PREPARED 상태가 아닙니다.")
    s = result.submission
    return AutoApprovalResponse(
        decision=result.decision,
        confidence=s.confidence,
        threshold=rules.AUTO_APPROVAL_THRESHOLD,
        liveness_passed=result.liveness_passed,
        submission_status=s.status,
        approval_path=s.approval_path,
    )


@router.get(
    "/submissions/{id}/review-share-preview",
    summary="[API-034] 확인 요청 공유 내용 미리보기",
    description=(
        "권한: OWNER. 확인자에게 보낼 내용을 신청자가 먼저 본다. PREPARED이고 자동 승인 대상이 아닌 건만. "
        "임시: 관절 선 리플레이·L1 요약·L2 이상치는 기능이 없어 null·빈 배열, 통증 안내 문구는 미정이라 null"
    ),
    response_model=SharePreviewResponse,
)
def api_034(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharePreviewResponse:
    try:
        content = service.share_preview(db, user.id, id)
    except service.SubmissionNotFound:
        raise _not_found()
    except service.NotOwner:
        raise AppError(403, "FORBIDDEN", "신청자 본인만 볼 수 있습니다.")
    except service.InvalidState:
        raise AppError(409, "INVALID_STATE", "이미 자동 승인되었거나 PREPARED 상태가 아닙니다.")
    return SharePreviewResponse(
        skeleton_replay_url=content.skeleton_replay_url,
        summary=content.summary,
        anomalies=[Anomaly(**a) for a in content.anomalies],
        pain_notice=content.pain_notice,
    )


@router.post(
    "/submissions/{id}/review-requests",
    summary="[API-035] 지인·길드장에게 확인 요청",
    description=(
        "권한: OWNER. If-Match 필수(제출건 version). PREPARED이고 자동 승인 대상이 아닌 건만, 제출건당 1건. "
        "확인자는 지금은 내 길드의 길드장만 고를 수 있다('지인' 정의 미정). "
        "본인 지정·미리보기 미확인은 400, 고를 수 없는 사람은 403, 이미 보냈거나 PREPARED가 아니면 409, version 불일치 412"
    ),
    status_code=201,
    response_model=ReviewRequestCreated,
)
def api_035(
    id: uuid.UUID,
    req: ReviewRequestCreate,
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewRequestCreated:
    expected_version = _parse_if_match(if_match)
    try:
        result = service.request_review(
            db, user.id, id, req.reviewer_user_id, req.share_preview_confirmed, expected_version
        )
    except service.InvalidRequest as e:
        raise AppError(
            400, "VALIDATION_FAILED", "본인을 지정했거나 미리보기를 확인하지 않았습니다.", {"reason": e.args[0]}
        )
    except service.SubmissionNotFound:
        raise _not_found()
    except service.NotOwner:
        raise AppError(403, "FORBIDDEN", "신청자 본인만 확인 요청을 보낼 수 있습니다.")
    except service.VersionMismatch as e:
        raise _concurrent_update(e.args[0])
    except service.InvalidState:
        raise AppError(409, "INVALID_STATE", "이미 확인 요청을 보냈거나 PREPARED 상태가 아닙니다.")
    except service.NotAllowedReviewer:
        raise AppError(403, "FORBIDDEN", "지인이나 길드장이 아닌 사람에게는 요청할 수 없습니다.")
    return ReviewRequestCreated(
        submission_id=result.submission.id,
        submission_status=result.submission.status,
        version=result.submission.version,
        reviewer=ReviewerRead(user_id=result.reviewer.id, nickname=result.reviewer.nickname),
        requested_at=result.review.requested_at,
    )


@router.get(
    "/me/review-requests",
    summary="[API-036] 받은 확인 요청 목록",
    description=(
        "권한: REVIEWER(로그인한 사용자 본인에게 온 요청만). status=PENDING(기본, 아직 처리 전) | ALL [제안: "
        "명세에 값 목록이 없음]. 최신순, cursor·limit(기본 20, 최대 50)"
    ),
    response_model=ReceivedReviewList,
)
def api_036(
    status: Literal["PENDING", "ALL"] = Query(default="PENDING"),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReceivedReviewList:
    try:
        page = service.list_received(
            db, user.id, pending_only=status == "PENDING", cursor=cursor, limit=limit
        )
    except service.InvalidCursor:
        raise _validation_failed("INVALID_CURSOR")
    return ReceivedReviewList(
        items=[
            ReceivedReviewItem(
                submission_id=i.submission.id,
                requester=RequesterRead(user_id=i.requester.id, nickname=i.requester.nickname),
                exercise_code=i.submission.exercise_code,
                counted_reps=i.submission.counted_reps,
                requested_at=i.review.requested_at,
            )
            for i in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/review-requests/{id}",
    summary="[API-037] 확인 자료 열람",
    description=(
        "권한: REVIEWER(요청받은 확인자만). id는 제출 ID. 얼굴·나이·길드명은 내려주지 않는다. "
        "응답 헤더 ETag에 제출건 version(승인·반려 때 If-Match에 넣음). "
        "임시: 관절 선 리플레이·L1·L2·통증 안내는 기능이 없어 null·빈 배열"
    ),
    response_model=ReviewMaterial,
)
def api_037(
    id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewMaterial:
    try:
        m = service.review_material(db, user.id, id)
    except service.ReviewNotFound:
        raise AppError(404, "NOT_FOUND", "확인 요청을 찾을 수 없습니다.")
    except service.NotReviewer:
        raise AppError(403, "FORBIDDEN", "요청받은 확인자만 열람할 수 있습니다.")
    s = m.submission
    response.headers["ETag"] = f'"{s.version}"'
    return ReviewMaterial(
        submission_id=s.id,
        status=s.status,
        version=s.version,
        requester=RequesterNickname(nickname=m.requester.nickname),
        exercise_code=s.exercise_code,
        counted_reps=s.counted_reps,
        confidence=s.confidence,
        skeleton_replay_url=m.content.skeleton_replay_url,
        summary=m.content.summary,
        anomalies=[Anomaly(**a) for a in m.content.anomalies],
        pain_notice=m.content.pain_notice,
    )


@router.post(
    "/review-requests/{id}/approve",
    summary="[API-038] 확인자 승인",
    description=(
        "권한: REVIEWER(요청받은 확인자만). If-Match 필수(제출건 version). PENDING_REVIEW → APPROVED(REVIEWER). "
        "취소와 동시에 오면 하나만 성공. 취소됐거나 이미 처리됐으면 409, version 불일치 412"
    ),
    response_model=ReviewApproved,
)
def api_038(
    id: uuid.UUID,
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewApproved:
    expected_version = _parse_if_match(if_match)
    try:
        s = service.approve_review(db, user.id, id, expected_version)
    except service.ReviewNotFound:
        raise AppError(404, "NOT_FOUND", "확인 요청을 찾을 수 없습니다.")
    except service.NotReviewer:
        raise AppError(403, "FORBIDDEN", "요청받은 확인자만 승인할 수 있습니다.")
    except service.VersionMismatch as e:
        raise _concurrent_update(e.args[0])
    except service.InvalidState:
        raise AppError(409, "INVALID_STATE", "취소되었거나 이미 처리된 요청입니다.")
    return ReviewApproved(
        submission_id=s.id, submission_status=s.status, approval_path=s.approval_path, version=s.version
    )


@router.post(
    "/review-requests/{id}/reject",
    summary="[API-039] 확인자 반려",
    description="권한: REVIEWER",
    status_code=501,
)
def api_039(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/reject-reasons",
    summary="[API-040] 반려 사유 코드 목록",
    description="권한: NONE",
    status_code=501,
)
def api_040() -> None:
    not_implemented()
