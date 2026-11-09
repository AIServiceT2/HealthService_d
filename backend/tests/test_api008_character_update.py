"""API-008 캐릭터 수정 — 노션 '전운시 API 명세서' API-008.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
수정 가능한 필드는 미정이라 avatarId만 받는다.
로그인은 실제 회원 가입·로그인으로 받은 access token을 쓴다 (tests/character_helpers.py).
"""

from tests.character_helpers import new_player


def _player_with_character(client, avatar_id="AVATAR_01"):
    user_id, headers = new_player(client)
    client.post("/characters", json={"avatarId": avatar_id}, headers=headers)
    return user_id, headers


def test_api008_update_avatar_returns_200(client):
    user_id, headers = _player_with_character(client)

    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=headers)

    assert res.status_code == 200
    assert res.json() == {"userId": str(user_id), "avatarId": "AVATAR_02", "exp": 0, "level": 1}
    # 조회에도 반영된다
    assert client.get("/characters/me", headers=headers).json()["avatarId"] == "AVATAR_02"


def test_api008_empty_body_changes_nothing(client):
    _, headers = _player_with_character(client)

    res = client.patch("/characters/me", json={}, headers=headers)

    assert res.status_code == 200
    assert res.json()["avatarId"] == "AVATAR_01"


def test_api008_only_own_character_is_updated(client):
    _, my_headers = _player_with_character(client)
    _, other_headers = _player_with_character(client)

    client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=my_headers)

    assert client.get("/characters/me", headers=other_headers).json()["avatarId"] == "AVATAR_01"


def test_api008_cannot_change_level_or_exp(client):
    _, headers = _player_with_character(client)

    res = client.patch("/characters/me", json={"level": 99, "exp": 9999}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
    body = client.get("/characters/me", headers=headers).json()
    assert body["level"] == 1
    assert body["exp"]["confirmed"] == 0


def test_api008_invalid_avatar_id_is_400(client):
    _, headers = _player_with_character(client)

    res = client.patch("/characters/me", json={"avatarId": 123}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api008_blank_avatar_id_is_400(client):
    _, headers = _player_with_character(client)

    res = client.patch("/characters/me", json={"avatarId": "   "}, headers=headers)

    assert res.status_code == 400
    assert client.get("/characters/me", headers=headers).json()["avatarId"] == "AVATAR_01"


def test_api008_docs_show_400_not_422(client):
    responses = client.get("/openapi.json").json()["paths"]["/characters/me"]["patch"]["responses"]

    assert "400" in responses
    assert "422" not in responses


def test_api008_without_character_is_404(client):
    _, headers = new_player(client)

    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api008_without_token_is_401(client):
    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
