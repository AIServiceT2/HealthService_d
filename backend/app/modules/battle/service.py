"""전투 상태 규칙. 체력은 저장하지 않고 '최대 체력 − 지급 완료(REWARDED) 건의 스냅샷 피해 합계'로 계산한다.

지급(API-041)이 피해를 따로 깎지 않아도 되고, 지급이 동시에 와도 값이 어긋나지 않는다.
피해가 들어가는 대상은 그 제출건의 세션에서 고른 공략 대상(target_type·target_id, API-020)이다.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.battle.catalog import DUNGEONS, GUILD_BOSS_HP_MAX, Dungeon
from app.modules.battle.models import GuildBoss
from app.modules.guild_chat import service as guild_chat_service
from app.modules.guild_chat.models import MessageType
from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission
from app.modules.workout_session.models import WorkoutSession
from app.modules.workout_session.service import KST

logger = logging.getLogger(__name__)

TARGET_DUNGEON = "DUNGEON"
TARGET_BOSS = "BOSS"


class DungeonNotFound(Exception):
    pass


class NotGuildMember(Exception):
    pass


def _damage_query(target_type: str, target_id: uuid.UUID):
    """그 대상을 고른 지급 완료 건의 스냅샷 피해 합계 (조건을 더 붙일 수 있게 select로 돌려줌)."""
    return (
        select(func.coalesce(func.sum(SubmissionSnapshot.total_damage), 0))
        .join(WorkoutSubmission, WorkoutSubmission.id == SubmissionSnapshot.submission_id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSubmission.session_id)
        .where(
            WorkoutSubmission.status == SubmissionStatus.REWARDED,
            WorkoutSession.target_type == target_type,
            WorkoutSession.target_id == target_id,
        )
    )


@dataclass(frozen=True)
class DungeonStatus:
    dungeon: Dungeon
    my_total_damage: int

    @property
    def enemy_hp(self) -> int:
        return max(self.dungeon.enemy_hp_max - self.my_total_damage, 0)


def get_dungeon_status(db: Session, user_id: uuid.UUID, dungeon_id: uuid.UUID) -> DungeonStatus:
    """던전은 개인 진행이다: 적 체력 = 최대 체력 − 내가 이 던전에 준 피해 (노션 API-045 예시 5000 − 1800 = 3200)."""
    dungeon = DUNGEONS.get(dungeon_id)
    if dungeon is None:
        raise DungeonNotFound(str(dungeon_id))
    mine = db.scalar(_damage_query(TARGET_DUNGEON, dungeon_id).where(WorkoutSubmission.user_id == user_id))
    return DungeonStatus(dungeon=dungeon, my_total_damage=int(mine))


# ---- 길드 주간 보스 (노션 API-046) ----

BOSS_ACTIVE = "ACTIVE"
BOSS_DEFEATED = "DEFEATED"


def week_start_kst(today: date | None = None) -> date:
    """그 주 월요일 (KST). 주 시작·마감은 명세 미정 → 월~일로 둠 [가안] (노션 예시 11-09(월)~11-15(일))."""
    today = today or datetime.now(KST).date()
    return today - timedelta(days=today.weekday())


@dataclass(frozen=True)
class BossStatus:
    boss: GuildBoss
    guild_total_damage: int

    @property
    def hp(self) -> int:
        return max(self.boss.hp_max - self.guild_total_damage, 0)

    @property
    def status(self) -> str:
        return BOSS_DEFEATED if self.hp == 0 else BOSS_ACTIVE

    @property
    def week_end(self) -> date:
        return self.boss.week_start + timedelta(days=6)


def get_or_create_week_boss(db: Session, guild_id: uuid.UUID, week_start: date) -> GuildBoss:
    """그 길드의 그 주 보스. 없으면 만든다. 여러 명이 동시에 처음 조회해도 (guild_id, week_start)
    유니크 제약 + ON CONFLICT DO NOTHING으로 하나만 생긴다."""
    created = db.execute(
        insert(GuildBoss)
        .values(id=uuid.uuid4(), guild_id=guild_id, week_start=week_start, hp_max=GUILD_BOSS_HP_MAX)
        .on_conflict_do_nothing(index_elements=[GuildBoss.guild_id, GuildBoss.week_start])
    ).rowcount
    db.commit()
    boss = db.scalars(
        select(GuildBoss).where(GuildBoss.guild_id == guild_id, GuildBoss.week_start == week_start)
    ).one()
    if created:
        # 그 주 보스가 처음 생기면 길드 채팅에 알린다 (JN-040). 실패해도 조회는 그대로
        try:
            guild_chat_service.post_boss_notice(
                db, guild_id, MessageType.BOSS_WEEK_STARTED, boss.week_start, boss.hp_max
            )
        except Exception:
            db.rollback()
            logger.exception("보스 등장 알림을 만들지 못했습니다 (guild_id=%s)", guild_id)
    return boss


def _guild_damage(db: Session, boss: GuildBoss) -> int:
    """지금 그 길드 소속원이 이 보스에 준 피해 합계 (API-046 guildTotalDamage와 같은 기준)."""
    members = select(User.id).where(User.guild_id == boss.guild_id)
    return int(db.scalar(_damage_query(TARGET_BOSS, boss.id).where(WorkoutSubmission.user_id.in_(members))))


def post_boss_defeated_if_needed(db: Session, submission_id: uuid.UUID) -> bool:
    """지급 완료(API-041) 뒤, 그 건의 공략 대상인 길드 보스 체력이 0이 되었으면 '보스 처치' 알림을 만든다 (JN-040).

    알림은 길드·주마다 한 번 (이미 있으면 False). 공략 대상이 보스가 아니면 아무것도 하지 않는다.
    """
    submission = db.get(WorkoutSubmission, submission_id)
    session = db.get(WorkoutSession, submission.session_id)
    if session.target_type != TARGET_BOSS or session.target_id is None:
        return False
    boss = db.get(GuildBoss, session.target_id)
    if boss is None or _guild_damage(db, boss) < boss.hp_max:
        return False
    return guild_chat_service.post_boss_notice(
        db, boss.guild_id, MessageType.BOSS_DEFEATED, boss.week_start, boss.hp_max
    )


def get_guild_boss_status(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, today: date | None = None
) -> BossStatus:
    """길드 소속원만 본다 (노션 API-046). 소속원이 아니거나 없는 길드면 NotGuildMember.

    guildTotalDamage는 '지금 그 길드 소속원'이 이 보스를 공략 대상으로 지급받은 건의 피해만 센다
    (세션 시작은 대상 ID를 검사하지 않아 다른 길드 사람 것을 막으려고. 소속 이력이 없어 탈퇴한 사람 몫은 빠짐).
    """
    requester = db.get(User, user_id)
    if requester is None or requester.guild_id != guild_id:
        raise NotGuildMember(str(user_id))
    boss = get_or_create_week_boss(db, guild_id, week_start_kst(today))
    return BossStatus(boss=boss, guild_total_damage=_guild_damage(db, boss))
