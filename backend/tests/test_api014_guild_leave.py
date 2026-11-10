"""API-014 길드 탈퇴 — 노션 '전운시 API 명세서' API-014.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요). 탈퇴 제한 정책은 미정이라 명세의 규칙(길드장 409)만 확인한다.
"""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import issue_code, new_guild


def _join(client, guild_id, leader_headers):
    code = issue_code(client, guild_id, leader_headers)
    user_id, headers = new_player(client)
    assert client.post("/guilds/join", json={"inviteCode": code}, headers=headers).status_code == 200
    return user_id, headers


def test_api014_member_leaves_204(client):
    guild_id, _, leader = new_guild(client)
    member_id, headers = _join(client, guild_id, leader)

    res = client.delete(f"/guilds/{guild_id}/members/me", headers=headers)

    assert res.status_code == 204
    assert res.content == b""
    assert client.get(f"/guilds/{guild_id}", headers=leader).json()["memberCount"] == 1
    ids = [i["userId"] for i in client.get(f"/guilds/{guild_id}/members", headers=leader).json()["items"]]
    assert str(member_id) not in ids


def test_api014_after_leaving_cannot_read_but_can_join_or_create(client):
    guild_id, _, leader = new_guild(client)
    _, headers = _join(client, guild_id, leader)
    client.delete(f"/guilds/{guild_id}/members/me", headers=headers)

    assert client.get(f"/guilds/{guild_id}", headers=headers).status_code == 403
    # 소속이 비어 새 길드를 만들 수 있다
    assert client.post("/guilds", json={"name": "새 길드"}, headers=headers).status_code == 201


def test_api014_leader_cannot_leave_409(client):
    guild_id, _, leader = new_guild(client)
    _join(client, guild_id, leader)

    res = client.delete(f"/guilds/{guild_id}/members/me", headers=leader)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"
    assert client.get(f"/guilds/{guild_id}", headers=leader).json()["memberCount"] == 2


def test_api014_leader_alone_cannot_leave_409(client):
    guild_id, _, leader = new_guild(client)

    res = client.delete(f"/guilds/{guild_id}/members/me", headers=leader)

    assert res.status_code == 409


def test_api014_non_member_is_403(client):
    guild_id, _, _ = new_guild(client)
    _, outsider = new_player(client)

    res = client.delete(f"/guilds/{guild_id}/members/me", headers=outsider)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api014_member_of_other_guild_stays_in_own_guild(client):
    guild_a, _, leader_a = new_guild(client, "길드A")
    guild_b, _, leader_b = new_guild(client, "길드B")
    _, member_b = _join(client, guild_b, leader_b)

    res = client.delete(f"/guilds/{guild_a}/members/me", headers=member_b)

    assert res.status_code == 403
    assert client.get(f"/guilds/{guild_b}", headers=member_b).status_code == 200


def test_api014_unknown_guild_is_403(client):
    _, headers = new_player(client)

    assert client.delete(f"/guilds/{uuid.uuid4()}/members/me", headers=headers).status_code == 403


def test_api014_without_token_is_401(client):
    guild_id, _, _ = new_guild(client)

    assert client.delete(f"/guilds/{guild_id}/members/me").status_code == 401
