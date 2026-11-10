"""길드 API 테스트 공통 도구."""

import uuid

from tests.character_helpers import new_player


def new_guild(client, name: str = "부산 스쿼터즈") -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
    """새 사용자가 길드를 만든다. (guild_id, 길드장 user_id, 길드장 헤더)를 돌려준다."""
    leader_id, headers = new_player(client)
    res = client.post("/guilds", json={"name": name}, headers=headers)
    assert res.status_code == 201, res.json()
    return uuid.UUID(res.json()["guildId"]), leader_id, headers
