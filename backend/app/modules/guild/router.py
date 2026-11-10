"""guild API. 노션 '전운시 API 명세서' API-009~017.

구현: API-009 길드 생성. 나머지는 경로만 있고 501을 돌려준다.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.guild import service
from app.modules.guild.schemas import ErrorResponse, GuildCreate, GuildCreated

# 입력 오류는 전역 처리기가 400 VALIDATION_FAILED로 돌려주므로, Swagger에 실제와 다른 422가
# 보이지 않게 공통 에러 본문을 4XX로 선언한다 (character 라우터와 같은 방식)
router = APIRouter(
    tags=["guild"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_UNAUTHENTICATED = {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."}


@router.post(
    "/guilds",
    summary="[API-009] 길드 생성",
    description="권한: PLAYER. name은 2~20자(앞뒤 공백 제외). 만든 사람이 길드장이 된다.",
    status_code=201,
    response_model=GuildCreated,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 다른 길드에 소속되어 있습니다."},
    },
)
def create_guild(
    body: GuildCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        guild = service.create_guild(db, user.id, body.name)
    except service.AlreadyInGuild:
        raise AppError(409, "INVALID_STATE", "이미 다른 길드에 소속되어 있습니다.")
    return GuildCreated(guild_id=guild.id, name=guild.name, leader_user_id=guild.leader_user_id)


@router.get(
    "/guilds/{guild_id}",
    summary="[API-010] 길드 정보 조회",
    description="권한: GUILD_MEMBER",
    status_code=501,
)
def api_010(guild_id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/guilds/{guild_id}/members",
    summary="[API-011] 길드원 목록",
    description="권한: GUILD_MEMBER",
    status_code=501,
)
def api_011(guild_id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/guilds/{guild_id}/invitations",
    summary="[API-012] 길드 초대 코드 발급",
    description="권한: GUILD_LEADER",
    status_code=501,
)
def api_012(guild_id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/guilds/join",
    summary="[API-013] 초대 코드로 길드 가입",
    description="권한: PLAYER",
    status_code=501,
)
def api_013() -> None:
    not_implemented()


@router.delete(
    "/guilds/{guild_id}/members/me",
    summary="[API-014] 길드 탈퇴",
    description="권한: GUILD_MEMBER",
    status_code=501,
)
def api_014(guild_id: uuid.UUID) -> None:
    not_implemented()


@router.delete(
    "/guilds/{guild_id}/members/{user_id}",
    summary="[API-015] 길드원 내보내기",
    description="권한: GUILD_LEADER",
    status_code=501,
)
def api_015(guild_id: uuid.UUID, user_id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/guilds/{guild_id}/leader",
    summary="[API-016] 길드장 위임",
    description="권한: GUILD_LEADER",
    status_code=501,
)
def api_016(guild_id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/me/acquaintances",
    summary="[API-017] 확인 요청 가능한 지인 목록",
    description="권한: PLAYER",
    status_code=501,
)
def api_017() -> None:
    not_implemented()
