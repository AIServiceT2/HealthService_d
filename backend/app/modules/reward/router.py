"""reward API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["reward"])


@router.post(
    "/internal/submissions/{id}/grant",
    summary="[API-041] 보상·피해 1회 반영",
    description="권한: SYSTEM",
    status_code=501,
)
def api_041(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/internal/reward-locks/release",
    summary="[API-042] 24시간 잠금 해제·능력치 확정 (배치)",
    description="권한: SYSTEM",
    status_code=501,
)
def api_042() -> None:
    not_implemented()


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
