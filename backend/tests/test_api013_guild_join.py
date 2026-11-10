"""API-013 초대 코드로 길드 가입 — 노션 '전운시 API 명세서' API-013.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요).
"""

from datetime import UTC, datetime, timedelta

from app.modules.guild.models import GuildInvitation
from tests.character_helpers import new_player
from tests.guild_helpers import issue_code, new_guild


def test_api013_join_with_code_returns_guild_id(client):
    guild_id, _, leader = new_guild(client)
    code = issue_code(client, guild_id, leader)
    member_id, headers = new_player(client)

    res = client.post("/guilds/join", json={"inviteCode": code}, headers=headers)

    assert res.status_code == 200
    assert res.json() == {"guildId": str(guild_id)}
    # 가입하면 소속원이 되어 길드 정보·목록을 볼 수 있다
    assert client.get(f"/guilds/{guild_id}", headers=headers).json()["memberCount"] == 2
    items = client.get(f"/guilds/{guild_id}/members", headers=headers).json()["items"]
    assert {"userId": str(member_id), "nickname": "플레이어", "role": "MEMBER"} in items


def test_api013_lowercase_and_spaces_are_accepted(client):
    guild_id, _, leader = new_guild(client)
    code = issue_code(client, guild_id, leader)
    _, headers = new_player(client)

    res = client.post("/guilds/join", json={"inviteCode": f" {code.lower()} "}, headers=headers)

    assert res.status_code == 200


def test_api013_same_code_can_be_used_by_many(client):
    guild_id, _, leader = new_guild(client)
    code = issue_code(client, guild_id, leader)

    for _ in range(3):
        _, headers = new_player(client)
        assert client.post("/guilds/join", json={"inviteCode": code}, headers=headers).status_code == 200

    assert client.get(f"/guilds/{guild_id}", headers=leader).json()["memberCount"] == 4


def test_api013_bad_format_is_400(client):
    _, headers = new_player(client)

    for bad in [{"inviteCode": "ABC"}, {"inviteCode": "ABCDEFG"}, {"inviteCode": "AB-12X"},
                {"inviteCode": 123456}, {}]:
        res = client.post("/guilds/join", json=bad, headers=headers)
        assert res.status_code == 400, bad
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_api013_unknown_code_is_404(client):
    _, headers = new_player(client)

    res = client.post("/guilds/join", json={"inviteCode": "ZZZZZ9"}, headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api013_expired_code_is_409(client, db):
    guild_id, _, leader = new_guild(client)
    code = issue_code(client, guild_id, leader)
    db.get(GuildInvitation, code).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    _, headers = new_player(client)

    res = client.post("/guilds/join", json={"inviteCode": code}, headers=headers)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"
    assert client.get(f"/guilds/{guild_id}", headers=headers).status_code == 403


def test_api013_already_in_guild_is_409(client):
    guild_id, _, leader = new_guild(client, "길드A")
    code = issue_code(client, guild_id, leader)
    other_guild, _, other_leader = new_guild(client, "길드B")

    res = client.post("/guilds/join", json={"inviteCode": code}, headers=other_leader)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"
    # 원래 길드 소속은 그대로
    assert client.get(f"/guilds/{other_guild}", headers=other_leader).status_code == 200


def test_api013_rejoin_same_guild_is_409(client):
    guild_id, _, leader = new_guild(client)
    code = issue_code(client, guild_id, leader)

    res = client.post("/guilds/join", json={"inviteCode": code}, headers=leader)

    assert res.status_code == 409


def test_api013_without_token_is_401(client):
    res = client.post("/guilds/join", json={"inviteCode": "A7K2QX"})

    assert res.status_code == 401
