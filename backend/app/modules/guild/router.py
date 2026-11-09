"""guild API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["guild"])


@router.post(
    "/guilds",
    summary="[API-009] 길드 생성",
    description="권한: PLAYER",
    status_code=501,
)
def api_009() -> None:
    not_implemented()


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
