"""API-075 길드 채팅 실시간 연결(WebSocket) — 노션 '전운시 API 명세서' API-075, 기능명세 JN-040 (별도 스토리 없음).

기대값은 노션 API-075의 요청·응답(READY·MESSAGE_CREATED·MESSAGE_DELETED·PING)과 닫기 코드(4401·4403),
API-014·015의 '연결을 4403으로 닫는다' 메모만 검사한다. AUTH 대기 시간·PING 간격은 [제안] 값이라
테스트에서는 짧게 바꿔 동작만 확인한다.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.modules.auth.service import ACCESS_TOKEN_TTL_SECONDS, create_access_token
from app.modules.guild_chat import router as chat_router
from app.modules.guild_chat.hub import hub
from tests.character_helpers import new_player
from tests.guild_helpers import add_member, new_guild


def _token(headers) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def _url(guild_id) -> str:
    return f"/guilds/{guild_id}/chat/ws"


def _ready(session, guild_id):
    assert session.receive_json() == {"type": "READY", "guildId": str(guild_id)}


def _closed_code(session) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        session.receive_json()
    return exc.value.code


def _send(client, guild_id, headers, body="실시간 메시지"):
    res = client.post(
        f"/guilds/{guild_id}/chat/messages",
        json={"clientMessageId": str(uuid.uuid4()), "body": body},
        headers=headers,
    )
    assert res.status_code in (200, 201), res.json()
    return res


def test_api075_member_gets_ready(client, db):
    guild_id, _, headers = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        _ready(ws, guild_id)


def test_api075_new_message_is_pushed_to_other_member(client, db):
    guild_id, _, leader_headers = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(member_headers)})
        _ready(ws, guild_id)
        sent = _send(client, guild_id, leader_headers, "다들 화이팅").json()

        event = ws.receive_json()

    assert event == {"type": "MESSAGE_CREATED", "message": sent}


def test_api075_resent_message_is_not_pushed_again(client, db):
    guild_id, _, headers = new_guild(client)
    client_message_id = str(uuid.uuid4())
    payload = {"clientMessageId": client_message_id, "body": "한 번만"}

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        _ready(ws, guild_id)
        client.post(f"/guilds/{guild_id}/chat/messages", json=payload, headers=headers)
        client.post(f"/guilds/{guild_id}/chat/messages", json=payload, headers=headers)
        _send(client, guild_id, headers, "다음 메시지")

        first = ws.receive_json()
        second = ws.receive_json()

    assert first["message"]["body"] == "한 번만"
    assert second["message"]["body"] == "다음 메시지"


def test_api075_deleted_message_is_pushed(client, db):
    guild_id, _, headers = new_guild(client)
    message_id = _send(client, guild_id, headers).json()["messageId"]

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        _ready(ws, guild_id)
        client.delete(f"/guilds/{guild_id}/chat/messages/{message_id}", headers=headers)

        event = ws.receive_json()

    assert event == {"type": "MESSAGE_DELETED", "messageId": message_id, "deletedBy": "AUTHOR"}


def test_api075_other_guild_does_not_receive(client, db):
    guild_a, _, headers_a = new_guild(client, name="길드에이")
    guild_b, _, headers_b = new_guild(client, name="길드비")

    with client.websocket_connect(_url(guild_b)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers_b)})
        _ready(ws, guild_b)
        _send(client, guild_a, headers_a, "에이 길드에만")
        _send(client, guild_b, headers_b, "비 길드에만")

        event = ws.receive_json()

    assert event["message"]["body"] == "비 길드에만"


def test_api075_ping(client, db, monkeypatch):
    monkeypatch.setattr(chat_router, "PING_INTERVAL_SECONDS", 0.05)
    guild_id, _, headers = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        _ready(ws, guild_id)

        assert ws.receive_json() == {"type": "PING"}
        ws.send_json({"type": "PONG"})
        assert ws.receive_json() == {"type": "PING"}


def test_api075_wrong_token_closes_4401(client, db):
    guild_id, _, _ = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": "not-a-token"})
        assert _closed_code(ws) == 4401


def test_api075_first_message_not_auth_closes_4401(client, db):
    guild_id, _, headers = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "PONG", "accessToken": _token(headers)})
        assert _closed_code(ws) == 4401


def test_api075_no_auth_in_time_closes_4401(client, db, monkeypatch):
    monkeypatch.setattr(chat_router, "AUTH_TIMEOUT_SECONDS", 0.05)
    guild_id, _, _ = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        assert _closed_code(ws) == 4401


def test_api075_expired_token_closes_4401(client, db):
    guild_id, leader_id, _ = new_guild(client)
    long_ago = datetime.now(UTC) - timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS + 60)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": create_access_token(leader_id, now=long_ago)})
        assert _closed_code(ws) == 4401


def test_api075_token_expiring_while_connected_closes_4401(client, db):
    guild_id, leader_id, _ = new_guild(client)
    # 1초 뒤 만료되는 토큰
    almost = datetime.now(UTC) - timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS - 1)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": create_access_token(leader_id, now=almost)})
        _ready(ws, guild_id)
        assert _closed_code(ws) == 4401


def test_api075_non_member_closes_4403(client, db):
    guild_id, _, _ = new_guild(client)
    _, outsider_headers = new_player(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(outsider_headers)})
        assert _closed_code(ws) == 4403


def test_api075_unknown_guild_closes_4403(client, db):
    _, headers = new_player(client)

    with client.websocket_connect(_url(uuid.uuid4())) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        assert _closed_code(ws) == 4403


def test_api075_leaving_guild_closes_4403(client, db):
    guild_id, _, _ = new_guild(client)
    _, member_headers = add_member(client, db, guild_id)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(member_headers)})
        _ready(ws, guild_id)
        res = client.delete(f"/guilds/{guild_id}/members/me", headers=member_headers)
        assert res.status_code == 204

        assert _closed_code(ws) == 4403


def test_api075_kicked_member_closes_4403_and_others_stay(client, db):
    guild_id, _, leader_headers = new_guild(client)
    kicked_id, kicked_headers = add_member(client, db, guild_id)

    with client.websocket_connect(_url(guild_id)) as leader_ws, client.websocket_connect(_url(guild_id)) as kicked_ws:
        leader_ws.send_json({"type": "AUTH", "accessToken": _token(leader_headers)})
        kicked_ws.send_json({"type": "AUTH", "accessToken": _token(kicked_headers)})
        _ready(leader_ws, guild_id)
        _ready(kicked_ws, guild_id)
        res = client.delete(f"/guilds/{guild_id}/members/{kicked_id}", headers=leader_headers)
        assert res.status_code == 204

        assert _closed_code(kicked_ws) == 4403
        _send(client, guild_id, leader_headers, "남은 사람에게")
        assert leader_ws.receive_json()["message"]["body"] == "남은 사람에게"


def test_api075_closed_connection_is_removed(client, db):
    guild_id, _, headers = new_guild(client)

    with client.websocket_connect(_url(guild_id)) as ws:
        ws.send_json({"type": "AUTH", "accessToken": _token(headers)})
        _ready(ws, guild_id)
        assert hub.connection_count(guild_id) == 1

    # 끊긴 뒤 메시지를 보내도 오류 없이 저장된다
    assert _send(client, guild_id, headers).status_code == 201
    assert hub.connection_count(guild_id) == 0
