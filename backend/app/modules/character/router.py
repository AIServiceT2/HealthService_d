"""character API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["character"])


@router.post(
    "/characters",
    summary="[API-006] 캐릭터 생성",
    description="권한: PLAYER",
    status_code=501,
)
def api_006() -> None:
    not_implemented()


@router.get(
    "/characters/me",
    summary="[API-007] 내 캐릭터·성장 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_007() -> None:
    not_implemented()


@router.patch(
    "/characters/me",
    summary="[API-008] 캐릭터 수정",
    description="권한: PLAYER",
    status_code=501,
)
def api_008() -> None:
    not_implemented()
