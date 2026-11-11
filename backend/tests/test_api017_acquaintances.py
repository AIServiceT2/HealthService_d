"""API-017 확인 요청 가능한 지인 목록 — 노션 '전운시 API 명세서' API-017, backlog US-07.

"지인" 정의는 미정이라 노션 가안(같은 길드원, 본인 제외)을 따른다. 확인 요청(API-035)도 이 목록에 있는
사람에게만 보낼 수 있다 (2026-11-11 팀 요청).
"""

from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild
from tests.review_helpers import new_prepared, request_review


def _acquaintances(client, headers):
    return client.get("/me/acquaintances", headers=headers)


def test_us07_api017_lists_same_guild_members_without_me_leader_first(client):
    guild_id, leader_id, leader = new_guild(client)
    member_a, a = join_with_code(client, guild_id, leader)
    member_b, _ = join_with_code(client, guild_id, leader)
    new_guild(client, "다른 길드")  # 다른 길드 사람은 나오지 않는다

    res = _acquaintances(client, a)

    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0] == {"userId": str(leader_id), "nickname": "플레이어", "relation": "GUILD_LEADER"}
    assert items[1:] == [{"userId": str(member_b), "nickname": "플레이어", "relation": "GUILD_MEMBER"}]
    assert str(member_a) not in {i["userId"] for i in items}


def test_us07_api017_leader_sees_members(client):
    guild_id, _, leader = new_guild(client)
    member_id, _ = join_with_code(client, guild_id, leader)

    items = _acquaintances(client, leader).json()["items"]

    assert items == [{"userId": str(member_id), "nickname": "플레이어", "relation": "GUILD_MEMBER"}]


def test_us07_api017_no_guild_is_empty(client):
    _, headers = new_player(client)

    res = _acquaintances(client, headers)

    assert res.status_code == 200
    assert res.json() == {"items": []}


def test_us07_api017_needs_token(client):
    res = client.get("/me/acquaintances")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_us07_api035_can_send_to_guild_member_in_acquaintances(client):
    """지인 목록의 길드원(길드장이 아니어도)에게 확인 요청을 보낼 수 있다."""
    guild_id, _, leader = new_guild(client)
    reviewer_id, _ = join_with_code(client, guild_id, leader)
    _, requester = join_with_code(client, guild_id, leader)
    sid, _ = new_prepared(client, confidence=0.82, headers=requester)

    res = request_review(client, sid, requester, reviewer_id)

    assert res.status_code == 201, res.json()
    assert res.json()["reviewer"]["userId"] == str(reviewer_id)


def test_us07_api035_leader_can_send_to_member(client):
    """길드장 본인의 애매한 건은 길드원에게 보낼 수 있다 (전에는 고를 사람이 없었음)."""
    guild_id, _, leader = new_guild(client)
    member_id, _ = join_with_code(client, guild_id, leader)
    sid, _ = new_prepared(client, confidence=0.82, headers=leader)

    assert request_review(client, sid, leader, member_id).status_code == 201


def test_us07_api035_other_guild_member_is_403(client):
    _, _, my_leader = new_guild(client, "내 길드")
    other_guild, _, other_leader = new_guild(client, "남의 길드")
    outsider_id, _ = join_with_code(client, other_guild, other_leader)
    sid, _ = new_prepared(client, confidence=0.82, headers=my_leader)

    res = request_review(client, sid, my_leader, outsider_id)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
