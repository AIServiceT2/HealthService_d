"""API-016 길드장 위임 — 노션 '전운시 API 명세서' API-016.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요). 본인 지정 409는 명세에 없는 제안 규칙.
"""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild


def test_api016_leader_delegates_to_member_200(client):
    guild_id, old_leader_id, old_leader = new_guild(client)
    member_id, member = join_with_code(client, guild_id, old_leader)

    res = client.post(f"/guilds/{guild_id}/leader", json={"userId": str(member_id)}, headers=old_leader)

    assert res.status_code == 200
    assert res.json() == {"guildId": str(guild_id), "leaderUserId": str(member_id)}
    info = client.get(f"/guilds/{guild_id}", headers=member).json()
    assert info["leader"]["userId"] == str(member_id)
    assert info["memberCount"] == 2
    roles = {i["userId"]: i["role"] for i in client.get(f"/guilds/{guild_id}/members", headers=member).json()["items"]}
    assert roles == {str(member_id): "LEADER", str(old_leader_id): "MEMBER"}


def test_api016_permissions_move_with_leadership(client):
    guild_id, _, old_leader = new_guild(client)
    member_id, new_leader = join_with_code(client, guild_id, old_leader)
    client.post(f"/guilds/{guild_id}/leader", json={"userId": str(member_id)}, headers=old_leader)

    # 새 길드장은 초대 코드를 발급할 수 있고, 이전 길드장은 못 한다
    assert client.post(f"/guilds/{guild_id}/invitations", headers=new_leader).status_code == 201
    assert client.post(f"/guilds/{guild_id}/invitations", headers=old_leader).status_code == 403
    # 이전 길드장은 이제 탈퇴할 수 있고, 새 길드장은 못 한다 (API-014)
    assert client.delete(f"/guilds/{guild_id}/members/me", headers=new_leader).status_code == 409
    assert client.delete(f"/guilds/{guild_id}/members/me", headers=old_leader).status_code == 204


def test_api016_member_cannot_delegate_403(client):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)
    other_id, _ = join_with_code(client, guild_id, leader)

    res = client.post(f"/guilds/{guild_id}/leader", json={"userId": str(other_id)}, headers=member)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api016_leader_of_other_guild_is_403(client):
    guild_a, _, leader_a = new_guild(client, "길드A")
    member_id, _ = join_with_code(client, guild_a, leader_a)
    _, _, leader_b = new_guild(client, "길드B")

    res = client.post(f"/guilds/{guild_a}/leader", json={"userId": str(member_id)}, headers=leader_b)

    assert res.status_code == 403


def test_api016_target_not_in_guild_is_404(client):
    guild_id, _, leader = new_guild(client, "길드A")
    outsider_id, _ = new_player(client)
    _, other_leader_id, _ = new_guild(client, "길드B")

    for target in (outsider_id, other_leader_id, uuid.uuid4()):
        res = client.post(f"/guilds/{guild_id}/leader", json={"userId": str(target)}, headers=leader)
        assert res.status_code == 404, target
        assert res.json()["code"] == "NOT_FOUND"


def test_api016_self_is_409(client):
    guild_id, leader_id, leader = new_guild(client)

    res = client.post(f"/guilds/{guild_id}/leader", json={"userId": str(leader_id)}, headers=leader)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_api016_invalid_body_is_400(client):
    guild_id, _, leader = new_guild(client)

    for bad in [{}, {"userId": "not-a-uuid"}, {"userId": str(uuid.uuid4()), "other": 1}]:
        res = client.post(f"/guilds/{guild_id}/leader", json=bad, headers=leader)
        assert res.status_code == 400, bad
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_api016_without_token_is_401(client):
    guild_id, _, leader = new_guild(client)
    member_id, _ = join_with_code(client, guild_id, leader)

    res = client.post(f"/guilds/{guild_id}/leader", json={"userId": str(member_id)})

    assert res.status_code == 401
