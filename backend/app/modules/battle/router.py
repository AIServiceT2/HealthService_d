"""battle API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["battle"])


@router.get(
    "/dungeons/{dungeon_id}",
    summary="[API-045] 던전 상태 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_045(dungeon_id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/guilds/{guild_id}/boss",
    summary="[API-046] 길드 보스 상태 조회",
    description="권한: GUILD_MEMBER",
    status_code=501,
)
def api_046(guild_id: uuid.UUID) -> None:
    not_implemented()
