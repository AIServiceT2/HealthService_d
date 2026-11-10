"""API-046 길드 보스 상태 조회 — 노션 '전운시 API 명세서' API-046.

보스는 길드·주(월~일, KST)마다 처음 조회할 때 만든다 (가안 HP 50000).
guildTotalDamage는 지금 길드 소속원의 지급 완료 건만 센다.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import app
from app.modules.battle.models import GuildBoss
from app.modules.battle.service import week_start_kst
from tests.battle_helpers import rewarded
from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild


def _boss(client, guild_id, headers):
    return client.get(f"/guilds/{guild_id}/boss", headers=headers)


def test_api046_first_lookup_creates_this_weeks_boss(client):
    guild_id, _, leader = new_guild(client)

    res = _boss(client, guild_id, leader)

    assert res.status_code == 200
    body = res.json()
    monday = week_start_kst()
    assert body["status"] == "ACTIVE"
    assert body["hpMax"] == body["hp"] == 50000
    assert body["guildTotalDamage"] == 0
    assert body["weekStart"] == monday.isoformat()
    assert body["weekEnd"] == (monday + timedelta(days=6)).isoformat()
    # 다시 조회해도 같은 보스
    assert _boss(client, guild_id, leader).json()["bossId"] == body["bossId"]


def test_api046_members_damage_adds_up(client, db):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)
    boss = ("BOSS", uuid.UUID(_boss(client, guild_id, leader).json()["bossId"]))

    rewarded(client, db, target=boss, headers=leader)
    rewarded(client, db, target=boss, headers=member)

    body = _boss(client, guild_id, member).json()
    assert body["guildTotalDamage"] == 1800
    assert body["hp"] == 48200


def test_api046_outsider_and_left_member_damage_not_counted(client, db):
    guild_id, _, leader = new_guild(client)
    _, leaver = join_with_code(client, guild_id, leader)
    boss = ("BOSS", uuid.UUID(_boss(client, guild_id, leader).json()["bossId"]))
    rewarded(client, db, target=boss)  # 다른 길드 사람이 bossId를 알고 공략
    rewarded(client, db, target=boss, headers=leaver)
    client.delete(f"/guilds/{guild_id}/members/me", headers=leaver)

    assert _boss(client, guild_id, leader).json()["guildTotalDamage"] == 0


def test_api046_defeated_when_hp_reaches_zero(client, db):
    guild_id, _, leader = new_guild(client)
    boss_id = _boss(client, guild_id, leader).json()["bossId"]
    db.get(GuildBoss, uuid.UUID(boss_id)).hp_max = 900  # 한 번(900)에 쓰러지게
    db.commit()

    rewarded(client, db, target=("BOSS", uuid.UUID(boss_id)), headers=leader)

    body = _boss(client, guild_id, leader).json()
    assert body["status"] == "DEFEATED"
    assert body["hp"] == 0


def test_api046_each_guild_has_own_boss(client):
    guild_a, _, leader_a = new_guild(client, "길드A")
    guild_b, _, leader_b = new_guild(client, "길드B")

    assert _boss(client, guild_a, leader_a).json()["bossId"] != _boss(client, guild_b, leader_b).json()["bossId"]


def test_api046_concurrent_first_lookups_make_one_boss(client, db):
    guild_id, _, leader = new_guild(client)

    def look(_):
        return TestClient(app).get(f"/guilds/{guild_id}/boss", headers=leader).json()["bossId"]

    with ThreadPoolExecutor(max_workers=5) as pool:
        ids = set(pool.map(look, range(5)))

    assert len(ids) == 1
    assert db.query(GuildBoss).count() == 1


def test_api046_week_is_monday_to_sunday_kst():
    assert week_start_kst(date(2026, 11, 9)) == date(2026, 11, 9)  # 월
    assert week_start_kst(date(2026, 11, 15)) == date(2026, 11, 9)  # 일
    assert week_start_kst(date(2026, 11, 16)) == date(2026, 11, 16)  # 다음 주 월
    # 기본값은 KST 오늘
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    assert week_start_kst() == today - timedelta(days=today.weekday())


def test_api046_non_member_is_403(client):
    guild_id, _, _ = new_guild(client)
    _, outsider = new_player(client)

    res = _boss(client, guild_id, outsider)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert _boss(client, uuid.uuid4(), outsider).status_code == 403


def test_api046_without_token_is_401(client):
    assert client.get(f"/guilds/{uuid.uuid4()}/boss").status_code == 401
