"""길드 API 테스트 공통 도구."""

import uuid

from tests.character_helpers import new_player


def new_guild(client, name: str = "부산 스쿼터즈") -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
    """새 사용자가 길드를 만든다. (guild_id, 길드장 user_id, 길드장 헤더)를 돌려준다."""
    leader_id, headers = new_player(client)
    res = client.post("/guilds", json={"name": name}, headers=headers)
    assert res.status_code == 201, res.json()
    return uuid.UUID(res.json()["guildId"]), leader_id, headers


def add_member(client, db, guild_id: uuid.UUID) -> tuple[uuid.UUID, dict[str, str]]:
    """새 사용자를 길드에 넣는다. 길드장 권한이 필요 없는 테스트용이라 DB에 guild_id를 직접 넣는다
    (초대 코드로 가입하는 실제 흐름은 join_with_code)."""
    from app.modules.auth.models import User

    user_id, headers = new_player(client)
    db.get(User, user_id).guild_id = guild_id
    db.commit()
    return user_id, headers


def issue_code(client, guild_id: uuid.UUID, leader_headers: dict[str, str], hours: int = 72) -> str:
    """길드장이 초대 코드를 발급한다 (API-012)."""
    res = client.post(f"/guilds/{guild_id}/invitations", json={"expiresInHours": hours}, headers=leader_headers)
    assert res.status_code == 201, res.json()
    return res.json()["inviteCode"]
