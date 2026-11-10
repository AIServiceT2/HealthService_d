"""submission API. 노션 '전운시 API 명세서' API-026·028·029·030.

로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import re
import uuid
from datetime import date


from fastapi import APIRouter, Body, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.submission import service
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.schemas import (
    CancelRequest,
    CancelResponse,
    ErrorResponse,
    SubmissionDetailRead,
    SubmissionList,
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
    description=(
        "권한: PLAYER. 본인 제출건만, 최신순(startedAt 내림차순). status 필터, from·to는 KST 날짜(둘 다 포함), "
        "cursor는 앞 응답의 nextCursor, limit 기본 20·최대 50. 항목 형식은 API-028과 같다."
    ),
    response_model=SubmissionList,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다. (status·기간·limit·cursor)"},
        401: _UNAUTHENTICATED,
    },
)
def list_my_submissions(
    status: SubmissionStatus | None = Query(default=None, description="상태 필터 (선택)"),
    date_from: date | None = Query(default=None, alias="from", description="시작 날짜 KST (선택, 예: 2026-11-01)"),
    date_to: date | None = Query(default=None, alias="to", description="끝 날짜 KST, 포함 (선택)"),
    cursor: str | None = Query(default=None, description="다음 페이지 커서"),
    limit: int = Query(default=20, ge=1, le=50, description="기본 20, 최대 50"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": "FROM_AFTER_TO"})
    try:
        page = service.list_my_submissions(
            db, user.id, status=status, date_from=date_from, date_to=date_to, cursor=cursor, limit=limit
        )
    except service.InvalidCursor:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": "INVALID_CURSOR"})
    return SubmissionList(items=[to_read(d) for d in page.items], next_cursor=page.next_cursor)


# If-Match 값: "3" 또는 3 (약한 ETag W/"3"도 받음)
_IF_MATCH = re.compile(r'^(?:W/)?"?(\d+)"?$')


def _parse_if_match(value: str) -> int:
    match = _IF_MATCH.fullmatch(value.strip())
    if match is None:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": "INVALID_IF_MATCH"})
    return int(match.group(1))


@stub_router.post(
    "/submissions/{id}/cancel",
    summary="[API-030] 승인 전 제출 취소",
    description=(
        "권한: OWNER. If-Match 필수(제출건 version, API-028의 ETag). SUBMITTED·PREPARED·PENDING_REVIEW만 "
        "취소되고 상한 예약을 해제한다. 승인과 동시에 오면 하나만 성공한다. reason은 선택이며 저장하지 않는다."
    ),
    response_model=CancelResponse,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED If-Match 없음·형식 오류, reason 200자 초과"},
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 신청자 본인만 취소할 수 있습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 제출건을 찾을 수 없습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 승인되었거나 종료된 제출건입니다."},
        412: {"model": ErrorResponse, "description": "CONCURRENT_UPDATE 다른 요청이 먼저 처리되었습니다. 최신 상태로 다시 시도하세요."},
    },
)
def cancel_submission(
    id: uuid.UUID,
    body: CancelRequest | None = Body(default=None),
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expected_version = _parse_if_match(if_match)
    try:
        result = service.cancel_submission(db, user.id, id, expected_version)
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.NotOwner:
        raise AppError(403, "FORBIDDEN", "신청자 본인만 취소할 수 있습니다.")
    except service.VersionMismatch as e:
        raise AppError(
            412, "CONCURRENT_UPDATE", "다른 요청이 먼저 처리되었습니다. 최신 상태로 다시 시도하세요.",
            {"currentVersion": e.args[0]},
        )
    except service.NotCancelable:
        raise AppError(409, "INVALID_STATE", "이미 승인되었거나 종료된 제출건입니다.")
    return CancelResponse(
        submission_id=result.submission.id,
        status=result.submission.status,
        released_reps=result.released_reps,
        version=result.submission.version,
    )
