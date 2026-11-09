"""auth API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/signup",
    summary="[API-001] 회원 가입",
    description="권한: NONE",
    status_code=501,
)
def api_001() -> None:
    not_implemented()


@router.post(
    "/auth/login",
    summary="[API-002] 로그인",
    description="권한: NONE",
    status_code=501,
)
def api_002() -> None:
    not_implemented()


@router.post(
    "/auth/refresh",
    summary="[API-003] 토큰 재발급",
    description="권한: NONE",
    status_code=501,
)
def api_003() -> None:
    not_implemented()


@router.post(
    "/auth/logout",
    summary="[API-004] 로그아웃",
    description="권한: PLAYER",
    status_code=501,
)
def api_004() -> None:
    not_implemented()


@router.get(
    "/me",
    summary="[API-005] 내 계정 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_005() -> None:
    not_implemented()
