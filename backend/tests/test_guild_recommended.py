"""추천 길드 목록·추천 길드 가입 — 시안 'F-01 길드 가입'의 추천 길드, 2026-11-11 팀 요청으로 더한 API.

노션 명세에 없는 API라 API ID가 없다. 길드 테스트(test_api013 등)와 같은 도구를 쓴다.
"""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def test_guild_recommended_orders_by_member_count_and_limits_to_3(client, db):
    new_guild(client, "작은 길드")
    big, _, _ = new_guild(client, "큰 길드")
    mid, _, _ = new_guild(client, "중간 길드")
    new_guild(client, "네번째 길드")
    for _ in range(2):
        add_member(client, db, big)
    add_member(client, db, mid)
    _, headers = new_player(client)

    res = client.get("/guilds/recommended", headers=headers)

    assert res.status_code == 200
    items = res.json()["items"]
    assert [i["guildId"] for i in items][:2] == [str(big), str(mid)]
    assert len(items) == 3
    assert items[0] == {"guildId": str(big), "name": "큰 길드", "memberCount": 3}
    # 길드원 수가 같으면 이름 순 (네번째 < 작은)
    assert items[2] == {"guildId": items[2]["guildId"], "name": "네번째 길드", "memberCount": 1}


def test_guild_recommended_needs_token(client):
    assert client.get("/guilds/recommended").status_code == 401


def test_guild_join_recommended(client):
    guild_id, _, _ = new_guild(client)
    _, headers = new_player(client)

    res = client.post(f"/guilds/{guild_id}/members/me", headers=headers)

    assert res.status_code == 200
    assert res.json() == {"guildId": str(guild_id)}
    assert client.get("/me", headers=headers).json()["guildId"] == str(guild_id)
    assert client.get(f"/guilds/{guild_id}", headers=headers).json()["memberCount"] == 2


def test_guild_join_recommended_already_in_guild_is_409(client):
    first, _, _ = new_guild(client, "첫 길드")
    second, _, _ = new_guild(client, "둘째 길드")
    _, headers = new_player(client)
    assert client.post(f"/guilds/{first}/members/me", headers=headers).status_code == 200

    res = client.post(f"/guilds/{second}/members/me", headers=headers)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_guild_join_recommended_unknown_is_404_and_needs_token(client):
    _, headers = new_player(client)

    assert client.post(f"/guilds/{uuid.uuid4()}/members/me", headers=headers).status_code == 404
    assert client.post(f"/guilds/{uuid.uuid4()}/members/me").status_code == 401
