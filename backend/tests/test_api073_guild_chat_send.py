"""API-073 길드 채팅 메시지 보내기 — 노션 '전운시 API 명세서' API-073, 기능명세 JN-040 (별도 스토리 없음).

기대값은 노션 API-073의 요청·응답·Error Code에 적힌 것만 검사한다.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.modules.guild_chat.models import GuildChatMessage
from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def _send(client, guild_id, headers, body="오늘 스쿼트 같이 해요!", client_message_id=None):
    payload = {"clientMessageId": str(client_message_id or uuid.uuid4()), "body": body}
    return client.post(f"/guilds/{guild_id}/chat/messages", json=payload, headers=headers)


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(GuildChatMessage))


def test_api073_member_sends_text_and_gets_201(client, db):
    guild_id, _, _ = new_guild(client)
    user_id, headers = add_member(client, db, guild_id)

    res = _send(client, guild_id, headers, body="오늘 스쿼트 같이 해요!")

    assert res.status_code == 201
    body = res.json()
    assert uuid.UUID(body["messageId"])
    assert body["type"] == "TEXT"
    assert body["sender"] == {"userId": str(user_id), "nickname": "플레이어"}
    assert body["body"] == "오늘 스쿼트 같이 해요!"
    assert body["payload"] is None
    assert body["deleted"] is False
    assert body["createdAt"]
    assert _count(db) == 1


def test_api073_leader_can_send(client, db):
    guild_id, _, leader_headers = new_guild(client)

    res = _send(client, guild_id, leader_headers)

    assert res.status_code == 201


def test_api073_body_is_trimmed(client, db):
    guild_id, _, headers = new_guild(client)

    res = _send(client, guild_id, headers, body="  화이팅  ")

    assert res.status_code == 201
    assert res.json()["body"] == "화이팅"


def test_api073_same_client_message_id_returns_first_message_with_200(client, db):
    guild_id, _, headers = new_guild(client)
    client_message_id = uuid.uuid4()
    first = _send(client, guild_id, headers, body="처음", client_message_id=client_message_id)

    again = _send(client, guild_id, headers, body="두 번째", client_message_id=client_message_id)

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json() == first.json()
    assert _count(db) == 1


def test_api073_concurrent_same_client_message_id_saves_once(client, db):
    guild_id, _, headers = new_guild(client)
    client_message_id = uuid.uuid4()

    def send(_):
        return _send(TestClient(app), guild_id, headers, client_message_id=client_message_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))

    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json()["messageId"] == results[1].json()["messageId"]
    assert _count(db) == 1


def test_api073_empty_or_blank_body_is_400(client, db):
    guild_id, _, headers = new_guild(client)

    for body in ["", "   "]:
        res = _send(client, guild_id, headers, body=body)
        assert res.status_code == 400
        assert res.json()["code"] == "VALIDATION_FAILED"
    assert _count(db) == 0


def test_api073_body_over_300_is_400(client, db):
    guild_id, _, headers = new_guild(client)

    assert _send(client, guild_id, headers, body="가" * 300).status_code == 201
    res = _send(client, guild_id, headers, body="가" * 301)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api073_cannot_send_notification_type(client, db):
    guild_id, _, headers = new_guild(client)

    res = client.post(
        f"/guilds/{guild_id}/chat/messages",
        json={"clientMessageId": str(uuid.uuid4()), "body": "보스 처치", "type": "BOSS_DEFEATED"},
        headers=headers,
    )

    assert res.status_code == 400
    assert _count(db) == 0


def test_api073_without_token_is_401(client, db):
    guild_id, _, _ = new_guild(client)

    res = _send(client, guild_id, {})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_api073_non_member_is_403(client, db):
    guild_id, _, _ = new_guild(client)
    _, outsider_headers = new_player(client)

    res = _send(client, guild_id, outsider_headers)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert _count(db) == 0


def test_api073_member_of_other_guild_is_403(client, db):
    guild_id, _, _ = new_guild(client, name="길드에이")
    _, _, other_headers = new_guild(client, name="길드비")

    res = _send(client, guild_id, other_headers)

    assert res.status_code == 403


def test_api073_unknown_guild_is_404(client, db):
    _, headers = new_player(client)

    res = _send(client, uuid.uuid4(), headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"
