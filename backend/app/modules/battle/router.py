"""battle API. 노션 '전운시 API 명세서' API-045·046.

구현: API-045 던전 상태 조회, API-046 길드 보스 상태 조회.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.battle import service
from app.modules.battle.schemas import (
    DungeonProgressRead,
    DungeonRead,
    EnemyRead,
    ErrorResponse,
    GuildBossRead,
)

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
    description=(
        "권한: GUILD_MEMBER. 이번 주(월~일, KST) 보스. 없으면 처음 조회할 때 만든다 (가안 HP 50000). "
        "hp = hpMax − guildTotalDamage, 0이면 DEFEATED. guildTotalDamage는 지금 길드 소속원이 이 보스를 "
        "대상으로 지급받은 건의 피해 합계 (탈퇴한 사람 몫은 빠짐). 보스를 처음 조회할 때 만들므로 404는 나오지 않는다."
    ),
    response_model=GuildBossRead,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드 소속원만 조회할 수 있습니다."},
    },
)
def read_guild_boss(
    guild_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        status = service.get_guild_boss_status(db, user.id, guild_id)
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 조회할 수 있습니다.")
    return GuildBossRead(
        boss_id=status.boss.id,
        status=status.status,
        hp_max=status.boss.hp_max,
        hp=status.hp,
        guild_total_damage=status.guild_total_damage,
        week_start=status.boss.week_start,
        week_end=status.week_end,
    )
