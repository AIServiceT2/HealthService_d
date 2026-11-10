"""API-012 길드 초대 코드 발급 — 노션 '전운시 API 명세서' API-012.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요). 기본 만료 72시간·1~168시간은 제안값 (명세는 기본값 미정).
"""

import re
import uuid
from datetime import UTC, datetime, timedelta

from app.modules.guild.models import GuildInvitation
from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def _expires_at(res) -> datetime:
    return datetime.fromisoformat(res.json()["expiresAt"].replace("Z", "+00:00"))


def test_api012_leader_issues_code_201(client, db):
    guild_id, leader_id, headers = new_guild(client)

    res = client.post(f"/guilds/{guild_id}/invitations", json={"expiresInHours": 24}, headers=headers)

    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"inviteCode", "expiresAt"}
    assert re.fullmatch(r"[A-Z0-9]{6}", body["inviteCode"])
    left = _expires_at(res) - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < left <= timedelta(hours=24)
    # GUILD_INVITATION 테이블에 저장된다 (노션 API-012)
    saved = db.get(GuildInvitation, body["inviteCode"])
    assert saved.guild_id == guild_id
    assert saved.created_by == leader_id


def test_api012_default_expiry_is_72_hours(client):
    guild_id, _, headers = new_guild(client)

    for res in (
        client.post(f"/guilds/{guild_id}/invitations", headers=headers),
        client.post(f"/guilds/{guild_id}/invitations", json={}, headers=headers),
    ):
        assert res.status_code == 201
        left = _expires_at(res) - datetime.now(UTC)
        assert timedelta(hours=71, minutes=59) < left <= timedelta(hours=72)


def test_api012_each_call_gives_new_code(client):
    guild_id, _, headers = new_guild(client)

    codes = {client.post(f"/guilds/{guild_id}/invitations", headers=headers).json()["inviteCode"] for _ in range(5)}

    assert len(codes) == 5


def test_api012_invalid_hours_is_400(client):
    guild_id, _, headers = new_guild(client)

    for bad in [{"expiresInHours": 0}, {"expiresInHours": 169}, {"expiresInHours": "72"},
                {"expiresInHours": 1.5}, {"other": 1}]:
        res = client.post(f"/guilds/{guild_id}/invitations", json=bad, headers=headers)
        assert res.status_code == 400, bad
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_api012_member_is_403(client, db):
    guild_id, _, _ = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)

    res = client.post(f"/guilds/{guild_id}/invitations", headers=member_headers)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api012_leader_of_other_guild_is_403(client):
    guild_id, _, _ = new_guild(client, "길드A")
    _, _, other_leader = new_guild(client, "길드B")

    res = client.post(f"/guilds/{guild_id}/invitations", headers=other_leader)

    assert res.status_code == 403


def test_api012_unknown_guild_is_403(client):
    _, headers = new_player(client)

    res = client.post(f"/guilds/{uuid.uuid4()}/invitations", headers=headers)

    assert res.status_code == 403


def test_api012_without_token_is_401(client):
    guild_id, _, _ = new_guild(client)

    res = client.post(f"/guilds/{guild_id}/invitations")

    assert res.status_code == 401
