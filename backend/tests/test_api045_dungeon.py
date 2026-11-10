"""API-045 던전 상태 조회 — 노션 '전운시 API 명세서' API-045.

던전은 코드 상수 1개(가안, battle/catalog.py). 적 체력 = hpMax − 내가 준 피해(지급 완료 건).
"""

import uuid

from app.modules.battle.catalog import DEMO_DUNGEON_ID
from tests.battle_helpers import rewarded
from tests.character_helpers import new_player
from tests.reward_helpers import approved_submission

DUNGEON = ("DUNGEON", DEMO_DUNGEON_ID)


def _dungeon(client, headers, dungeon_id=DEMO_DUNGEON_ID):
    return client.get(f"/dungeons/{dungeon_id}", headers=headers)


def test_api045_new_player_sees_full_hp(client):
    _, headers = new_player(client)

    res = _dungeon(client, headers)

    assert res.status_code == 200
    assert res.json() == {
        "id": str(DEMO_DUNGEON_ID),
        "name": "초원 던전",
        "enemy": {"name": "고블린", "hpMax": 5000, "hp": 5000},
        "myProgress": {"totalDamage": 0},
    }


def test_api045_rewarded_damage_lowers_my_enemy_hp(client, db):
    _, headers = rewarded(client, db, target=DUNGEON, counted=30)  # 30타 × 30 = 900
    rewarded(client, db, target=DUNGEON, counted=30, headers=headers)

    body = _dungeon(client, headers).json()

    assert body["myProgress"] == {"totalDamage": 1800}
    assert body["enemy"]["hp"] == 3200  # 노션 API-045 예시와 같은 값


def test_api045_progress_is_per_player(client, db):
    """던전은 개인 진행: 다른 사람이 준 피해는 내 적 체력에 영향이 없다."""
    rewarded(client, db, target=DUNGEON)
    _, me = new_player(client)

    assert _dungeon(client, me).json()["enemy"]["hp"] == 5000


def test_api045_only_rewarded_and_this_dungeon_count(client, db):
    _, headers = rewarded(client, db, target=None)  # 대상을 고르지 않은 건
    rewarded(client, db, target=("BOSS", uuid.uuid4()), headers=headers)  # 다른 대상
    approved_submission(client, db, headers=headers)  # 지급 전(APPROVED) 건

    assert _dungeon(client, headers).json()["myProgress"]["totalDamage"] == 0


def test_api045_hp_does_not_go_below_zero(client, db):
    _, headers = new_player(client)
    for _ in range(6):  # 900 × 6 = 5400 > 5000
        rewarded(client, db, target=DUNGEON, headers=headers)

    body = _dungeon(client, headers).json()

    assert body["myProgress"]["totalDamage"] == 5400
    assert body["enemy"]["hp"] == 0


def test_api045_unknown_dungeon_is_404(client):
    _, headers = new_player(client)

    res = _dungeon(client, headers, uuid.uuid4())

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api045_without_token_is_401(client):
    assert client.get(f"/dungeons/{DEMO_DUNGEON_ID}").status_code == 401
