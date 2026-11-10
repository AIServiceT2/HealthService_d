"""reward API. 노션 '전운시 API 명세서' API-041~044.

구현: API-041 보상·피해 1회 반영, API-042 24시간 잠금 해제. 나머지는 경로만 있고 501을 돌려준다.
/internal API는 서버 내부 호출 전용 (X-Internal-Token, snapshot/internal.py).
"""

import uuid

from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.reward import service
from app.modules.reward.schemas import (
    AppliedRead,
    DamageRead,
    ErrorResponse,
    GrantResponse,
    ItemRef,
    ReleaseRequest,
    ReleaseResponse,
)
from app.modules.snapshot.internal import require_internal_token

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["reward"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_INTERNAL_401 = {"model": ErrorResponse, "description": "UNAUTHENTICATED 서버 내부 호출 전용입니다."}


@router.post(
    "/internal/submissions/{id}/grant",
    summary="[API-041] 보상·피해 1회 반영",
    description=(
        "권한: SYSTEM (서버 내부 호출 전용, X-Internal-Token). Idempotency-Key 필수. "
        "스냅샷 값만큼 경험치·아이템을 한 트랜잭션으로 반영하고 APPROVED → REWARDED. "
        "같은 키로 다시 부르면 첫 결과를 alreadyGranted: true로, 다른 키면 409 ALREADY_REWARDED. "
        "아이템은 24시간 LOCKED. 캐릭터가 없으면 409 (명세에 없음, 제안). "
        "임시: 피해는 던전·보스 모델이 없어 결과에만 담고, 능력치 경험치는 반영하지 않는다."
    ),
    response_model=GrantResponse,
    response_model_by_alias=True,
    responses={
        401: _INTERNAL_401,
        404: {"model": ErrorResponse, "description": "NOT_FOUND 제출건을 찾을 수 없습니다."},
        409: {
            "model": ErrorResponse,
            "description": "INVALID_STATE APPROVED 상태가 아닙니다. / ALREADY_REWARDED 다른 요청으로 이미 지급되었습니다.",
        },
    },
    dependencies=[Depends(require_internal_token)],
)
def grant(
    id: uuid.UUID,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    try:
        result = service.grant(db, id, idempotency_key)
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.AlreadyRewarded:
        raise AppError(409, "ALREADY_REWARDED", "다른 요청으로 이미 지급되었습니다.")
    except service.NotApproved:
        raise AppError(409, "INVALID_STATE", "APPROVED 상태가 아닙니다.")
    except service.NoCharacter:
        raise AppError(409, "INVALID_STATE", "캐릭터가 없어 지급할 수 없습니다.", {"reason": "NO_CHARACTER"})
    return GrantResponse(
        submission_id=result.submission_id,
        already_granted=result.already_granted,
        applied=AppliedRead(
            exp=result.exp,
            items=[ItemRef(item_id=i.id, status=i.status) for i in result.items],
            damage=DamageRead(
                target_type=result.damage.target_type,
                target_id=result.damage.target_id,
                amount=result.damage.amount,
            ),
        ),
        rewarded_at=result.rewarded_at,
    )


@router.post(
    "/internal/reward-locks/release",
    summary="[API-042] 24시간 잠금 해제·능력치 확정 (배치)",
    description=(
        "권한: SYSTEM (서버 내부 호출 전용, X-Internal-Token). 본문 선택: now(테스트용 기준 시각). "
        "지급 뒤 24시간이 지난(같은 시각 포함, 제안) LOCKED 아이템을 UNLOCKED로 바꾼다. "
        "confirmedStats는 능력치 모델이 미정이라 0. 해제 뒤 상태명 UNLOCKED는 제안, 실행 방식(스케줄)은 미정."
    ),
    response_model=ReleaseResponse,
    response_model_by_alias=True,
    responses={401: _INTERNAL_401},
    dependencies=[Depends(require_internal_token)],
)
def release_locks(
    body: ReleaseRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    result = service.release_locks(db, body.now if body else None)
    return ReleaseResponse(released_items=result.released_items, confirmed_stats=result.confirmed_stats)


@router.get(
    "/me/rewards",
    summary="[API-043] 내 지급 내역",
    description="권한: PLAYER",
    status_code=501,
)
def api_043() -> None:
    not_implemented()


@router.get(
    "/me/inventory",
    summary="[API-044] 인벤토리 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_044() -> None:
    not_implemented()
