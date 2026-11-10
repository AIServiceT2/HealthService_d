"""API-010 길드 정보 조회 — 노션 '전운시 API 명세서' API-010.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요).
가입 API(API-013)가 아직 없어 소속원 수 2명 이상은 DB에서 guild_id를 직접 넣어 만든다.
"""

import uuid

from app.modules.auth.models import User
from tests.character_helpers import new_player
from tests.guild_helpers import new_guild


def test_api010_member_reads_guild_info(client):
    guild_id, leader_id, headers = new_guild(client)

    res = client.get(f"/guilds/{guild_id}", headers=headers)

    assert res.status_code == 200
    assert res.json() == {
        "id": str(guild_id),
        "name": "부산 스쿼터즈",
        "leader": {"userId": str(leader_id), "nickname": "플레이어"},
        "memberCount": 1,
    }


def test_api010_member_count_counts_all_members(client, db):
    guild_id, _, headers = new_guild(client)
    member_id, member_headers = new_player(client)
    db.get(User, member_id).guild_id = guild_id
    db.commit()

    res = client.get(f"/guilds/{guild_id}", headers=member_headers)

    assert res.status_code == 200
    assert res.json()["memberCount"] == 2


def test_api010_non_member_is_403(client):
    guild_id, _, _ = new_guild(client)
    _, outsider = new_player(client)

    res = client.get(f"/guilds/{guild_id}", headers=outsider)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api010_member_of_other_guild_is_403(client):
    guild_id, _, _ = new_guild(client, "길드A")
    _, _, other_leader = new_guild(client, "길드B")

    res = client.get(f"/guilds/{guild_id}", headers=other_leader)

    assert res.status_code == 403


def test_api010_unknown_guild_is_404(client):
    _, headers = new_player(client)

    res = client.get(f"/guilds/{uuid.uuid4()}", headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api010_invalid_guild_id_is_400(client):
    _, headers = new_player(client)

    res = client.get("/guilds/not-a-uuid", headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api010_without_token_is_401(client):
    guild_id, _, _ = new_guild(client)

    res = client.get(f"/guilds/{guild_id}")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
