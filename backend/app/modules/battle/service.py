"""전투 상태 규칙. 체력은 저장하지 않고 '최대 체력 − 지급 완료(REWARDED) 건의 스냅샷 피해 합계'로 계산한다.

지급(API-041)이 피해를 따로 깎지 않아도 되고, 지급이 동시에 와도 값이 어긋나지 않는다.
피해가 들어가는 대상은 그 제출건의 세션에서 고른 공략 대상(target_type·target_id, API-020)이다.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.battle.catalog import DUNGEONS, Dungeon
from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission
from app.modules.workout_session.models import WorkoutSession

TARGET_DUNGEON = "DUNGEON"
TARGET_BOSS = "BOSS"


class DungeonNotFound(Exception):
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
