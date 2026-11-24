"""API-074 길드 채팅 메시지 삭제(숨김) — 노션 '전운시 API 명세서' API-074, 기능명세 JN-040 (별도 스토리 없음).

기대값은 노션 API-074의 요청·응답·Error Code와 JN-040 '본인은 자기 TEXT만, 길드장은 모든 메시지'만 검사한다.
알림 메시지는 아직 만드는 곳이 없어(자동 알림은 다음 단계) DB에 직접 넣는다.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.modules.guild_chat.models import GuildChatMessage, MessageType
from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def _send(client, guild_id, headers, body="지울 수도 있는 메시지"):
    res = client.post(
        f"/guilds/{guild_id}/chat/messages",
        json={"clientMessageId": str(uuid.uuid4()), "body": body},
        headers=headers,
    )
    assert res.status_code == 201, res.json()
    return res.json()["messageId"]


def _delete(client, guild_id, message_id, headers):
    return client.delete(f"/guilds/{guild_id}/chat/messages/{message_id}", headers=headers)


def _items(client, guild_id, headers):
    return client.get(f"/guilds/{guild_id}/chat/messages", headers=headers).json()["items"]


def _notification(db, guild_id) -> str:
    message = GuildChatMessage(
        guild_id=guild_id, type=MessageType.BOSS_DEFEATED, payload={"weekStart": "2026-11-23", "hpMax": 50000}
    )
    db.add(message)
    db.commit()
    return str(message.id)


def test_api074_author_hides_own_text(client, db):
    guild_id, _, _ = new_guild(client)
    _, headers = add_member(client, db, guild_id)
    message_id = _send(client, guild_id, headers)

    res = _delete(client, guild_id, message_id, headers)

    assert res.status_code == 200
    assert res.json() == {"messageId": message_id, "deleted": True, "deletedBy": "AUTHOR"}
    item = _items(client, guild_id, headers)[0]
    assert item["messageId"] == message_id
    assert item["deleted"] is True
    assert item["body"] is None


def test_api074_hidden_row_is_kept(client, db):
    guild_id, _, headers = new_guild(client)
    message_id = _send(client, guild_id, headers)

    _delete(client, guild_id, message_id, headers)

    message = db.get(GuildChatMessage, uuid.UUID(message_id))
    assert message is not None
    assert message.deleted_at is not None


def test_api074_leader_hides_member_text(client, db):
    guild_id, leader_id, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    message_id = _send(client, guild_id, member_headers)

    res = _delete(client, guild_id, message_id, leader_headers)

    assert res.status_code == 200
    assert res.json()["deletedBy"] == "LEADER"
    assert db.get(GuildChatMessage, uuid.UUID(message_id)).deleted_by == leader_id


def test_api074_leader_hides_own_text_as_author(client, db):
    guild_id, _, leader_headers = new_guild(client)
    message_id = _send(client, guild_id, leader_headers)

    res = _delete(client, guild_id, message_id, leader_headers)

    assert res.json()["deletedBy"] == "AUTHOR"


def test_api074_leader_hides_notification(client, db):
    guild_id, _, leader_headers = new_guild(client)
    message_id = _notification(db, guild_id)

    res = _delete(client, guild_id, message_id, leader_headers)

    assert res.status_code == 200
    assert res.json()["deletedBy"] == "LEADER"


def test_api074_member_cannot_hide_others_text(client, db):
    guild_id, _, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    message_id = _send(client, guild_id, leader_headers)

    res = _delete(client, guild_id, message_id, member_headers)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert _items(client, guild_id, member_headers)[0]["deleted"] is False


def test_api074_member_cannot_hide_notification(client, db):
    guild_id, _, _ = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    message_id = _notification(db, guild_id)

    res = _delete(client, guild_id, message_id, member_headers)

    assert res.status_code == 403


def test_api074_again_returns_same_result(client, db):
    guild_id, _, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    message_id = _send(client, guild_id, member_headers)
    first = _delete(client, guild_id, message_id, leader_headers)
    hidden_at = db.get(GuildChatMessage, uuid.UUID(message_id)).deleted_at

    again = _delete(client, guild_id, message_id, member_headers)

    assert again.status_code == 200
    assert again.json() == first.json()
    db.expire_all()
    assert db.get(GuildChatMessage, uuid.UUID(message_id)).deleted_at == hidden_at


def test_api074_concurrent_deletes_hide_once(client, db):
    guild_id, _, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    message_id = _send(client, guild_id, member_headers)

    def delete(headers):
        return _delete(TestClient(app), guild_id, message_id, headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(delete, [leader_headers, member_headers]))

    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()


def test_api074_without_token_is_401(client, db):
    guild_id, _, headers = new_guild(client)
    message_id = _send(client, guild_id, headers)

    assert _delete(client, guild_id, message_id, {}).status_code == 401


def test_api074_non_member_is_403(client, db):
    guild_id, _, headers = new_guild(client)
    message_id = _send(client, guild_id, headers)
    _, outsider_headers = new_player(client)

    res = _delete(client, guild_id, message_id, outsider_headers)

    assert res.status_code == 403


def test_api074_unknown_message_is_404(client, db):
    guild_id, _, headers = new_guild(client)

    res = _delete(client, guild_id, uuid.uuid4(), headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api074_message_of_other_guild_is_404(client, db):
    guild_a, _, headers_a = new_guild(client, name="길드에이")
    guild_b, _, headers_b = new_guild(client, name="길드비")
    other = _send(client, guild_b, headers_b)

    res = _delete(client, guild_a, other, headers_a)

    assert res.status_code == 404
    assert _items(client, guild_b, headers_b)[0]["deleted"] is False
