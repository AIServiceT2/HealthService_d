"""auth API. 노션 '전운시 API 명세서' API-001~005.

로그인 방식은 PRD에서 미정이라 노션 명세의 가안(EMAIL, access 30분·refresh 14일)대로 만든다.
아직 구현하지 않은 API는 501을 돌려준다.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.stub import not_implemented
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LoginUser,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)

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
    description="권한: NONE. 이메일·비밀번호 불일치는 401 UNAUTHENTICATED",
    response_model=LoginResponse,
)
def api_002(req: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user, tokens = service.login(db, req)
    return LoginResponse(
        access_token=tokens.access_token,
        access_token_expires_in=tokens.access_token_expires_in,
        refresh_token=tokens.refresh_token,
        user=LoginUser(id=user.id, nickname=user.nickname, guild_id=user.guild_id),
    )


@router.post(
    "/auth/refresh",
    summary="[API-003] 토큰 재발급",
    description="권한: NONE. refresh 토큰도 새로 발급하고 이전 토큰은 폐기(rotation). "
    "만료·폐기된 토큰은 401 UNAUTHENTICATED",
    response_model=TokenResponse,
)
def api_003(req: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    tokens = service.refresh(db, req.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        access_token_expires_in=tokens.access_token_expires_in,
        refresh_token=tokens.refresh_token,
    )


@router.post(
    "/auth/logout",
    summary="[API-004] 로그아웃",
    description="권한: PLAYER. 전달한 refresh 토큰을 폐기한다. Bearer 토큰이 없거나 유효하지 않으면 "
    "401 UNAUTHENTICATED",
    status_code=204,
)
def api_004(
    req: RefreshRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.logout(db, user.id, req.refresh_token)
    return Response(status_code=204)


@router.get(
    "/me",
    summary="[API-005] 내 계정 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_005() -> None:
    not_implemented()
