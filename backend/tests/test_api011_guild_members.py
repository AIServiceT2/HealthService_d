"""API-011 길드원 목록 — 노션 '전운시 API 명세서' API-011.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요).
"""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import add_member, join_with_code, new_guild


def test_api011_lists_members_by_user_id_with_roles(client, db):
    guild_id, leader_id, headers = new_guild(client)
    member_ids = [add_member(client, db, guild_id)[0] for _ in range(2)]

    res = client.get(f"/guilds/{guild_id}/members", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["nextCursor"] is None
    expected_ids = sorted([leader_id, *member_ids])
    assert [i["userId"] for i in body["items"]] == [str(i) for i in expected_ids]
    roles = {i["userId"]: i["role"] for i in body["items"]}
    assert roles[str(leader_id)] == "LEADER"
    assert all(roles[str(m)] == "MEMBER" for m in member_ids)
    assert {"userId": str(leader_id), "nickname": "플레이어", "role": "LEADER"} in body["items"]


def test_api011_member_can_list(client, db):
    guild_id, _, _ = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)

    res = client.get(f"/guilds/{guild_id}/members", headers=member_headers)

    assert res.status_code == 200
    assert len(res.json()["items"]) == 2


def test_api011_pages_with_cursor_without_gaps_or_duplicates(client, db):
    guild_id, _, headers = new_guild(client)
    for _ in range(4):
        add_member(client, db, guild_id)

    seen, cursor = [], None
    for _ in range(10):
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        body = client.get(f"/guilds/{guild_id}/members", params=params, headers=headers).json()
        assert len(body["items"]) <= 2
        seen += [i["userId"] for i in body["items"]]
        cursor = body["nextCursor"]
        if cursor is None:
            break

    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_api011_leader_change_during_paging_has_no_gaps_or_duplicates(client):
    """페이지를 넘기는 중에 길드장이 바뀌어도 모든 길드원이 한 번씩만 나온다 (검토에서 찾은 버그)."""
    guild_id, _, leader = new_guild(client)
    member_ids = sorted(join_with_code(client, guild_id, leader)[0] for _ in range(4))

    first = client.get(f"/guilds/{guild_id}/members", params={"limit": 2}, headers=leader).json()
    # 첫 쪽을 본 뒤 user_id가 가장 큰 길드원에게 위임
    client.post(f"/guilds/{guild_id}/leader", json={"userId": str(member_ids[-1])}, headers=leader)
    seen, cursor = [i["userId"] for i in first["items"]], first["nextCursor"]
    while cursor:
        body = client.get(
            f"/guilds/{guild_id}/members", params={"limit": 2, "cursor": cursor}, headers=leader
        ).json()
        seen += [i["userId"] for i in body["items"]]
        cursor = body["nextCursor"]

    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_api011_other_guild_members_are_not_listed(client, db):
    guild_id, _, headers = new_guild(client, "길드A")
    other_guild, other_leader, _ = new_guild(client, "길드B")

    ids = [i["userId"] for i in client.get(f"/guilds/{guild_id}/members", headers=headers).json()["items"]]

    assert str(other_leader) not in ids


def test_api011_non_member_is_403(client):
    guild_id, _, _ = new_guild(client)
    _, outsider = new_player(client)

    res = client.get(f"/guilds/{guild_id}/members", headers=outsider)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api011_unknown_guild_is_403(client):
    """명세의 에러는 403뿐이라 없는 길드도 소속원이 아닌 경우로 본다."""
    _, headers = new_player(client)

    res = client.get(f"/guilds/{uuid.uuid4()}/members", headers=headers)

    assert res.status_code == 403


def test_api011_limit_out_of_range_is_400(client):
    guild_id, _, headers = new_guild(client)

    for limit in (0, 51, "abc"):
        res = client.get(f"/guilds/{guild_id}/members", params={"limit": limit}, headers=headers)
        assert res.status_code == 400, limit
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_api011_broken_cursor_is_400(client):
    guild_id, _, headers = new_guild(client)

    res = client.get(f"/guilds/{guild_id}/members", params={"cursor": "not-a-cursor"}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api011_without_token_is_401(client):
    guild_id, _, _ = new_guild(client)

    res = client.get(f"/guilds/{guild_id}/members")

    assert res.status_code == 401
