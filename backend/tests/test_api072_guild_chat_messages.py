"""API-072 길드 채팅 메시지 목록 — 노션 '전운시 API 명세서' API-072, 기능명세 JN-040 (별도 스토리 없음).

기대값은 노션 API-072의 요청·응답·Error Code에 적힌 것만 검사한다.
숨긴 메시지·알림 메시지는 아직 만드는 API가 없어(API-074, 자동 알림) DB에 직접 넣는다.
"""

import uuid
from datetime import UTC, datetime

from app.modules.guild_chat.models import GuildChatMessage, MessageType
from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def _send(client, guild_id, headers, body):
    res = client.post(
        f"/guilds/{guild_id}/chat/messages",
        json={"clientMessageId": str(uuid.uuid4()), "body": body},
        headers=headers,
    )
    assert res.status_code == 201, res.json()
    return res.json()


def _list(client, guild_id, headers, **params):
    return client.get(f"/guilds/{guild_id}/chat/messages", headers=headers, params=params)


def _bodies(res) -> list[str]:
    return [m["body"] for m in res.json()["items"]]


def test_api072_returns_messages_oldest_first(client, db):
    guild_id, _, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)
    _send(client, guild_id, leader_headers, "첫째")
    _send(client, guild_id, member_headers, "둘째")
    _send(client, guild_id, leader_headers, "셋째")

    res = _list(client, guild_id, member_headers)

    assert res.status_code == 200
    body = res.json()
    assert _bodies(res) == ["첫째", "둘째", "셋째"]
    assert body["nextCursor"] is None
    assert body["hasMoreAfter"] is False


def test_api072_item_has_spec_fields(client, db):
    guild_id, leader_id, headers = new_guild(client)
    sent = _send(client, guild_id, headers, "안녕")

    item = _list(client, guild_id, headers).json()["items"][0]

    assert item == sent
    assert set(item) == {"messageId", "type", "sender", "body", "payload", "createdAt", "deleted"}
    assert item["sender"]["userId"] == str(leader_id)


def test_api072_empty_guild_returns_no_items(client, db):
    guild_id, _, headers = new_guild(client)

    res = _list(client, guild_id, headers)

    assert res.status_code == 200
    assert res.json() == {"items": [], "nextCursor": None, "hasMoreAfter": False}


def test_api072_latest_page_then_cursor_for_older(client, db):
    guild_id, _, headers = new_guild(client)
    for i in range(5):
        _send(client, guild_id, headers, f"m{i}")

    first = _list(client, guild_id, headers, limit=2)
    assert _bodies(first) == ["m3", "m4"]
    assert first.json()["nextCursor"] is not None

    second = _list(client, guild_id, headers, limit=2, cursor=first.json()["nextCursor"])
    assert _bodies(second) == ["m1", "m2"]

    last = _list(client, guild_id, headers, limit=2, cursor=second.json()["nextCursor"])
    assert _bodies(last) == ["m0"]
    assert last.json()["nextCursor"] is None


def test_api072_after_returns_newer_messages(client, db):
    guild_id, _, headers = new_guild(client)
    sent = [_send(client, guild_id, headers, f"m{i}") for i in range(5)]

    res = _list(client, guild_id, headers, after=sent[1]["messageId"], limit=2)

    assert res.status_code == 200
    assert _bodies(res) == ["m2", "m3"]
    assert res.json()["hasMoreAfter"] is True
    assert res.json()["nextCursor"] is None

    rest = _list(client, guild_id, headers, after=res.json()["items"][-1]["messageId"], limit=2)
    assert _bodies(rest) == ["m4"]
    assert rest.json()["hasMoreAfter"] is False


def test_api072_after_latest_message_returns_nothing(client, db):
    guild_id, _, headers = new_guild(client)
    last = _send(client, guild_id, headers, "마지막")

    res = _list(client, guild_id, headers, after=last["messageId"])

    assert res.json()["items"] == []
    assert res.json()["hasMoreAfter"] is False


def test_api072_only_messages_of_that_guild(client, db):
    guild_a, _, headers_a = new_guild(client, name="길드에이")
    guild_b, _, headers_b = new_guild(client, name="길드비")
    _send(client, guild_a, headers_a, "에이 메시지")
    _send(client, guild_b, headers_b, "비 메시지")

    assert _bodies(_list(client, guild_a, headers_a)) == ["에이 메시지"]


def test_api072_deleted_message_keeps_place_without_body(client, db):
    guild_id, _, headers = new_guild(client)
    sent = _send(client, guild_id, headers, "지울 메시지")
    message = db.get(GuildChatMessage, uuid.UUID(sent["messageId"]))
    message.deleted_at = datetime.now(UTC)
    db.commit()

    item = _list(client, guild_id, headers).json()["items"][0]

    assert item["messageId"] == sent["messageId"]
    assert item["deleted"] is True
    assert item["body"] is None
    assert item["payload"] is None


def test_api072_notification_has_payload_and_no_sender(client, db):
    guild_id, _, headers = new_guild(client)
    db.add(
        GuildChatMessage(
            guild_id=guild_id,
            type=MessageType.BOSS_DEFEATED,
            payload={"weekStart": "2026-11-23", "hpMax": 50000},
        )
    )
    db.commit()

    item = _list(client, guild_id, headers).json()["items"][0]

    assert item["type"] == "BOSS_DEFEATED"
    assert item["sender"] is None
    assert item["body"] is None
    assert item["payload"] == {"weekStart": "2026-11-23", "hpMax": 50000}


def test_api072_cursor_and_after_together_is_400(client, db):
    guild_id, _, headers = new_guild(client)
    sent = _send(client, guild_id, headers, "m0")
    _send(client, guild_id, headers, "m1")
    cursor = _list(client, guild_id, headers, limit=1).json()["nextCursor"]
    assert cursor is not None

    res = _list(client, guild_id, headers, cursor=cursor, after=sent["messageId"])

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api072_bad_cursor_is_400(client, db):
    guild_id, _, headers = new_guild(client)

    res = _list(client, guild_id, headers, cursor="not-a-cursor")

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api072_after_message_of_other_guild_is_400(client, db):
    guild_a, _, headers_a = new_guild(client, name="길드에이")
    guild_b, _, headers_b = new_guild(client, name="길드비")
    other = _send(client, guild_b, headers_b, "비 메시지")

    res = _list(client, guild_a, headers_a, after=other["messageId"])

    assert res.status_code == 400


def test_api072_limit_out_of_range_is_400(client, db):
    guild_id, _, headers = new_guild(client)

    assert _list(client, guild_id, headers, limit=0).status_code == 400
    assert _list(client, guild_id, headers, limit=51).status_code == 400


def test_api072_without_token_is_401(client, db):
    guild_id, _, _ = new_guild(client)

    res = _list(client, guild_id, {})

    assert res.status_code == 401


def test_api072_non_member_is_403(client, db):
    guild_id, _, headers = new_guild(client)
    _send(client, guild_id, headers, "길드원만 봄")
    _, outsider_headers = new_player(client)

    res = _list(client, guild_id, outsider_headers)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_api072_unknown_guild_is_404(client, db):
    _, headers = new_player(client)

    res = _list(client, uuid.uuid4(), headers)

    assert res.status_code == 404
