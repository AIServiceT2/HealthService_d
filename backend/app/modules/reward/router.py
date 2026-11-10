"""reward API. 노션 '전운시 API 명세서' API-041~044.

구현: API-041 보상·피해 1회 반영, API-042 24시간 잠금 해제, API-043 내 지급 내역, API-044 인벤토리 조회.
/internal API는 서버 내부 호출 전용 (X-Internal-Token, snapshot/internal.py).
"""

import uuid

from fastapi import APIRouter, Body, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.reward import service
from app.modules.reward.schemas import (
    AppliedRead,
    DamageRead,
    ErrorResponse,
    GrantResponse,
    InventoryItemRead,
    InventoryRead,
    ItemRef,
    ReleaseRequest,
    ReleaseResponse,
    RewardEntryRead,
    RewardList,
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
    description=(
        "권한: PLAYER. 본인 지급 내역만, 최신 지급순(정렬은 제안). 수치는 스냅샷 값, "
        "protectionEndsAt = rewardedAt + 24시간. cursor는 앞 응답의 nextCursor, limit 기본 20·최대 50."
    ),
    response_model=RewardList,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다. (limit·cursor)"},
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED Bearer 토큰이 필요하거나 유효하지 않습니다."},
    },
)
def list_my_rewards(
    cursor: str | None = Query(default=None, description="다음 페이지 커서"),
    limit: int = Query(default=20, ge=1, le=50, description="기본 20, 최대 50"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        page = service.list_my_rewards(db, user.id, cursor, limit)
    except service.InvalidCursor:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": "INVALID_CURSOR"})
    return RewardList(
        items=[
            RewardEntryRead(
                submission_id=e.submission_id,
                exp=e.exp,
                items=[ItemRef(item_id=i.id, status=i.status) for i in e.items],
                damage=e.damage,
                rewarded_at=e.rewarded_at,
                protection_ends_at=e.protection_ends_at,
            )
            for e in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/me/inventory",
    summary="[API-044] 인벤토리 조회",
    description=(
        "권한: PLAYER. 본인 아이템 전부(페이지 나눔 없음), 최신 지급순(제안). unlockAt = 지급 시각 + 24시간. "
        "status는 LOCKED / UNLOCKED(해제 뒤 상태명은 제안). 아이템 카탈로그는 미정이라 종류·이름은 없다."
    ),
    response_model=InventoryRead,
    response_model_by_alias=True,
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED Bearer 토큰이 필요하거나 유효하지 않습니다."},
    },
)
def my_inventory(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return InventoryRead(
        items=[
            InventoryItemRead(
                item_id=i.item.id,
                submission_id=i.item.submission_id,
                status=i.item.status,
                unlock_at=i.unlock_at,
            )
            for i in service.my_inventory(db, user.id)
        ]
    )
