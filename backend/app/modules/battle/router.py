"""battle API. 노션 '전운시 API 명세서' API-045·046.

구현: API-045 던전 상태 조회. API-046은 경로만 있고 501을 돌려준다.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.battle import service
from app.modules.battle.schemas import DungeonProgressRead, DungeonRead, EnemyRead, ErrorResponse

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["battle"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_UNAUTHENTICATED = {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."}


@router.get(
    "/dungeons/{dungeon_id}",
    summary="[API-045] 던전 상태 조회",
    description=(
        "권한: PLAYER. 던전은 개인 진행: 적 hp = hpMax − 내가 이 던전에 준 피해(지급 완료 건의 스냅샷 피해 합계). "
        "가안: 던전 테이블이 없어 데모 던전 1개를 코드 상수로 둔다 (battle/catalog.py, ID 고정)."
    ),
    response_model=DungeonRead,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        404: {"model": ErrorResponse, "description": "NOT_FOUND 던전을 찾을 수 없습니다."},
    },
)
def read_dungeon(
    dungeon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        status = service.get_dungeon_status(db, user.id, dungeon_id)
    except service.DungeonNotFound:
        raise AppError(404, "NOT_FOUND", "던전을 찾을 수 없습니다.")
    return DungeonRead(
        id=status.dungeon.id,
        name=status.dungeon.name,
        enemy=EnemyRead(name=status.dungeon.enemy_name, hp_max=status.dungeon.enemy_hp_max, hp=status.enemy_hp),
        my_progress=DungeonProgressRead(total_damage=status.my_total_damage),
    )


@router.get(
    "/guilds/{guild_id}/boss",
    summary="[API-046] 길드 보스 상태 조회",
    description="권한: GUILD_MEMBER",
    status_code=501,
)
def api_046(guild_id: uuid.UUID) -> None:
    not_implemented()
