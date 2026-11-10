"""API-015 길드원 내보내기 — 노션 '전운시 API 명세서' API-015.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요).
"""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild


def test_api015_leader_kicks_member_204(client):
    guild_id, _, leader = new_guild(client)
    member_id, member = join_with_code(client, guild_id, leader)

    res = client.delete(f"/guilds/{guild_id}/members/{member_id}", headers=leader)

    assert res.status_code == 204
    assert res.content == b""
    assert client.get(f"/guilds/{guild_id}", headers=leader).json()["memberCount"] == 1
    # 내보내진 사람은 더 이상 조회할 수 없고, 다시 가입할 수 있다
    assert client.get(f"/guilds/{guild_id}", headers=member).status_code == 403
    assert client.post("/guilds", json={"name": "새 길드"}, headers=member).status_code == 201


def test_api015_member_cannot_kick_403(client):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)
    other_id, _ = join_with_code(client, guild_id, leader)

    res = client.delete(f"/guilds/{guild_id}/members/{other_id}", headers=member)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert client.get(f"/guilds/{guild_id}", headers=leader).json()["memberCount"] == 3


def test_api015_leader_cannot_kick_self_403(client):
    guild_id, leader_id, leader = new_guild(client)

    res = client.delete(f"/guilds/{guild_id}/members/{leader_id}", headers=leader)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert client.get(f"/guilds/{guild_id}", headers=leader).status_code == 200


def test_api015_leader_of_other_guild_is_403(client):
    guild_a, _, leader_a = new_guild(client, "길드A")
    member_id, _ = join_with_code(client, guild_a, leader_a)
    _, _, leader_b = new_guild(client, "길드B")

    res = client.delete(f"/guilds/{guild_a}/members/{member_id}", headers=leader_b)

    assert res.status_code == 403


def test_api015_target_not_in_guild_is_404(client):
    guild_id, _, leader = new_guild(client)
    outsider_id, _ = new_player(client)

    for target in (outsider_id, uuid.uuid4()):
        res = client.delete(f"/guilds/{guild_id}/members/{target}", headers=leader)
        assert res.status_code == 404, target
        assert res.json()["code"] == "NOT_FOUND"


def test_api015_member_of_other_guild_is_404_and_untouched(client):
    guild_a, _, leader_a = new_guild(client, "길드A")
    guild_b, _, leader_b = new_guild(client, "길드B")
    member_b_id, member_b = join_with_code(client, guild_b, leader_b)

    res = client.delete(f"/guilds/{guild_a}/members/{member_b_id}", headers=leader_a)

    assert res.status_code == 404
    assert client.get(f"/guilds/{guild_b}", headers=member_b).status_code == 200


def test_api015_without_token_is_401(client):
    guild_id, _, leader = new_guild(client)
    member_id, _ = join_with_code(client, guild_id, leader)

    assert client.delete(f"/guilds/{guild_id}/members/{member_id}").status_code == 401
