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
    """새 사용자를 길드에 넣는다. 가입 API(API-013)가 생기기 전까지 DB에 guild_id를 직접 넣는다."""
    from app.modules.auth.models import User

    user_id, headers = new_player(client)
    db.get(User, user_id).guild_id = guild_id
    db.commit()
    return user_id, headers
