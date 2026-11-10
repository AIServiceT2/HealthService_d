"""던전 카탈로그 (노션 API-045). 

던전 테이블은 노션 DB에 아직 없다 (명세: '적 모델·체력은 미정이며, 던전 테이블은 아직 DB에 없습니다').
MVP 데모용으로 던전 1개를 코드 상수로 둔다 [가안·팀 확인 필요]. 값은 노션 API-045 예시 그대로.
ID는 고정이라 앱이 세션 시작(API-020) 때 target {type: DUNGEON, id}로 그대로 쓸 수 있다.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Dungeon:
    id: uuid.UUID
    name: str
    enemy_name: str
    enemy_hp_max: int


DEMO_DUNGEON_ID = uuid.UUID("3d1f6c2a-5b7e-4c1a-9f0e-2a8b6d4c1e70")

DUNGEONS: dict[uuid.UUID, Dungeon] = {
    DEMO_DUNGEON_ID: Dungeon(id=DEMO_DUNGEON_ID, name="초원 던전", enemy_name="고블린", enemy_hp_max=5000),
}
