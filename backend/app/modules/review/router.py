"""review API. 노션 '전운시 API 명세서' API-033~040 (backlog US-03·07·08).

로그인 확인은 auth 모듈의 get_current_user (Bearer access token).
/internal 경로는 snapshot 모듈의 require_internal_token(X-Internal-Token)을 같이 쓴다.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.review import rules, service
from app.modules.review.schemas import AutoApprovalResponse, ErrorResponse
from app.modules.snapshot.internal import require_internal_token

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["review"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)


def _not_found() -> AppError:
    return AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")


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
    description="권한: OWNER",
    status_code=501,
)
def api_034(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/submissions/{id}/review-requests",
    summary="[API-035] 지인·길드장에게 확인 요청",
    description="권한: OWNER",
    status_code=501,
)
def api_035(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/me/review-requests",
    summary="[API-036] 받은 확인 요청 목록",
    description="권한: REVIEWER",
    status_code=501,
)
def api_036() -> None:
    not_implemented()


@router.get(
    "/review-requests/{id}",
    summary="[API-037] 확인 자료 열람",
    description="권한: REVIEWER",
    status_code=501,
)
def api_037(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/review-requests/{id}/approve",
    summary="[API-038] 확인자 승인",
    description="권한: REVIEWER",
    status_code=501,
)
def api_038(id: uuid.UUID) -> None:
    not_implemented()


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
