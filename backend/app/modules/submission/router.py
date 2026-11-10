"""submission API. 노션 '전운시 API 명세서' API-026·028·029·030.

로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import uuid

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.submission import service
from app.modules.submission.schemas import (
    ErrorResponse,
    SubmissionDetailRead,
    SubmitRequest,
    SubmitResponse,
)

_ERRORS_4XX = {"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}}
_UNAUTHENTICATED = {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."}

router = APIRouter(prefix="/submissions", tags=["submission"], responses=_ERRORS_4XX)


def to_read(detail: service.SubmissionDetail) -> SubmissionDetailRead:
    s = detail.submission
    return SubmissionDetailRead(
        id=s.id,
        session_id=s.session_id,
        exercise_code=s.exercise_code,
        status=s.status,
        version=s.version,
        approval_path=s.approval_path,
        started_at=s.started_at,
        ended_at=s.ended_at,
        counted_reps=s.counted_reps,
        reserved_reps=detail.reserved_reps,
        confidence=s.confidence,
        liveness_passed=detail.liveness_passed,
    )


def owner_errors(fn):
    """SubmissionNotFound → 404, NotOwner → 403 으로 바꿔 던진다."""
    try:
        return fn()
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.NotOwner:
        raise AppError(403, "FORBIDDEN", "본인 제출건만 조회할 수 있습니다.")


@router.get(
    "/{submission_id}",
    summary="[API-028] 제출 상태 조회",
    description=(
        "권한: OWNER. 응답 헤더 ETag에 제출건 version (취소·확인 요청 때 If-Match에 넣음). "
        "reservedReps는 해제되지 않은 상한 예약량 (취소·반려로 해제되면 0)."
    ),
    response_model=SubmissionDetailRead,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 본인 제출건만 조회할 수 있습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 제출건을 찾을 수 없습니다."},
    },
)
def read_submission(
    submission_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = owner_errors(lambda: service.get_submission_detail(db, user.id, submission_id))
    response.headers["ETag"] = f'"{detail.submission.version}"'
    return to_read(detail)


# ---- 노션 API 명세서 API-026·029·030 ----
# 경로가 /submissions로 시작하지 않는 것도 있어 prefix 없는 라우터를 따로 둔다.
# 입력 오류는 전역 처리기가 400으로 돌려주므로, Swagger에 실제와 다른 422가 보이지 않게
# 공통 에러 본문을 4XX로 선언한다 (API-026의 422 SERVER_RECOUNT_MISMATCH는 따로 적음)
stub_router = APIRouter(tags=["submission"], responses=_ERRORS_4XX)


@stub_router.post(
    "/workout-sessions/{id}/submit",
    summary="[API-026] 세션 종료·운동 제출",
    description=(
        "권한: OWNER. Idempotency-Key 필수, 같은 키로 다시 보내면 첫 결과를 돌려준다. "
        "청크 1..totalChunks가 모두 있어야 한다. 그날 상한이 다 찼으면 제출건은 만들고 reservedReps는 0. "
        "임시: 서버 재계산은 ai/ 엔진 연결 전이라 reps 중 counted=true 수를 쓰고, "
        "confidence는 앱이 보낸 aiConfidence를 저장한다."
    ),
    status_code=202,
    response_model=SubmitResponse,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 누락된 청크가 있거나 입력값이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 본인 세션만 제출할 수 있습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 세션을 찾을 수 없습니다."},
        409: {
            "model": ErrorResponse,
            "description": "DUPLICATE_SUBMISSION 같은 시간대에 활성 제출건이 있습니다. / INVALID_STATE 이미 제출했거나 폐기된 세션입니다.",
        },
        422: {"model": ErrorResponse, "description": "SERVER_RECOUNT_MISMATCH 인정 렙 수가 서버 재계산 값보다 큽니다."},
    },
)
def submit_session(
    id: uuid.UUID,
    body: SubmitRequest,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = service.submit_session(
        db,
        user.id,
        id,
        idempotency_key=idempotency_key,
        total_chunks=body.total_chunks,
        ended_at=body.ended_at,
        client_rep_count=body.client_rep_count,
        reps=[service.RepIn(rep_no=r.rep_no, ts=r.ts, counted=r.counted) for r in body.reps],
        ai_confidence=body.ai_confidence,
    )
    submission = result.submission
    # 다시 보낸 요청에도 '첫 결과'를 돌려준다: 접수 직후 상태(SUBMITTED, version 0)
    return SubmitResponse(
        submission_id=submission.id,
        status="SUBMITTED",
        counted_reps=submission.counted_reps,
        reserved_reps=result.reserved_reps,
        version=0,
    )


@stub_router.get(
    "/me/submissions",
    summary="[API-029] 내 제출 목록",
    description="권한: PLAYER",
    status_code=501,
)
def api_029() -> None:
    not_implemented()


@stub_router.post(
    "/submissions/{id}/cancel",
    summary="[API-030] 승인 전 제출 취소",
    description="권한: OWNER",
    status_code=501,
)
def api_030(id: uuid.UUID) -> None:
    not_implemented()
