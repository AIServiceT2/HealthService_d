"""auth API. 노션 '전운시 API 명세서' API-001~005.

로그인 방식은 PRD에서 미정이라 노션 명세의 가안(EMAIL, access 30분·refresh 14일)대로 만든다.
아직 구현하지 않은 API는 501을 돌려준다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.stub import not_implemented
from app.modules.auth import service
from app.modules.auth.schemas import SignupRequest, SignupResponse

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/signup",
    summary="[API-001] 회원 가입",
    description="권한: NONE. 14세 미만·이메일 중복·형식 오류는 400 VALIDATION_FAILED",
    status_code=201,
    response_model=SignupResponse,
)
def api_001(req: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    user = service.signup(db, req)
    return SignupResponse(user_id=user.id)


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
