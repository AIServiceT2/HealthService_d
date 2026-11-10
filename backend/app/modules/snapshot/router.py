"""snapshot API. 노션 '전운시 API 명세서' API-031·032.

구현: API-031 보상 스냅샷 계산·고정. API-032는 경로만 있고 501을 돌려준다.
"""

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.snapshot import service
from app.modules.snapshot.internal import require_internal_token
from app.modules.snapshot.schemas import ErrorResponse, SnapshotRead

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["snapshot"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)


@router.post(
    "/internal/submissions/{id}/snapshot",
    summary="[API-031] 보상 스냅샷 계산·고정",
    description=(
        "권한: SYSTEM (서버 내부 호출 전용, X-Internal-Token). Idempotency-Key 필수. "
        "SUBMITTED → PREPARED. 이미 계산한 건은 같은 스냅샷을 돌려준다. 스쿼트 1회 = 1타, "
        "타격 수는 일일 상한 안의 보상 대상 인정량 기준. exp·피해·드랍은 명세 예시 비율의 가안."
    ),
    response_model=SnapshotRead,
    response_model_by_alias=True,
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED 서버 내부 호출 전용입니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 제출건을 찾을 수 없습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE SUBMITTED 상태가 아닙니다."},
        500: {"model": ErrorResponse, "description": "INTERNAL_ERROR 보상 계산 실패 (SUBMITTED 유지, 다시 호출)"},
    },
    dependencies=[Depends(require_internal_token)],
)
def prepare_snapshot(
    id: uuid.UUID,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    # Idempotency-Key는 형식만 검사한다. 이미 계산한 건은 키와 관계없이 같은 스냅샷을 돌려줘
    # 결과가 같으므로 따로 저장하지 않는다 [제안·팀 확인 필요]
    try:
        snapshot = service.prepare_snapshot(db, id)
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.NotSubmitted:
        raise AppError(409, "INVALID_STATE", "SUBMITTED 상태가 아닙니다.")
    except service.CalculationError as e:
        raise AppError(500, "INTERNAL_ERROR", "보상 계산에 실패했습니다.", {"reason": str(e)})
    return SnapshotRead.model_validate(snapshot)


@router.get(
    "/submissions/{id}/reward-preview",
    summary="[API-032] 보상·타격 수 미리보기",
    description="권한: OWNER",
    status_code=501,
)
def api_032(id: uuid.UUID) -> None:
    not_implemented()
