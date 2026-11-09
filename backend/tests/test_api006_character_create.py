"""API-006 캐릭터 생성 — 노션 '전운시 API 명세서' API-006.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
로그인은 실제 회원 가입·로그인으로 받은 access token을 쓴다 (tests/character_helpers.py).
"""

from tests.character_helpers import new_player


def test_api006_create_character_returns_201_level1_exp0(client):
    user_id, headers = new_player(client)

    res = client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=headers)

    assert res.status_code == 201
    assert res.json() == {"userId": str(user_id), "avatarId": "AVATAR_01", "exp": 0, "level": 1}


def test_api006_avatar_id_is_optional(client):
    _, headers = new_player(client)

    res = client.post("/characters", headers=headers)

    assert res.status_code == 201
    assert res.json()["avatarId"] is None


def test_api006_second_character_for_same_user_is_409(client):
    _, headers = new_player(client)
    client.post("/characters", json={}, headers=headers)

    res = client.post("/characters", json={"avatarId": "AVATAR_02"}, headers=headers)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_api006_other_user_can_create_own_character(client):
    _, first = new_player(client)
    _, second = new_player(client)
    client.post("/characters", json={}, headers=first)

    res = client.post("/characters", json={}, headers=second)

    assert res.status_code == 201


def test_api006_without_token_is_401(client):
    res = client.post("/characters", json={})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_api006_invalid_token_is_401(client):
    """임시 방식(토큰 = 사용자 UUID)이 더는 통하지 않는다."""
    user_id, _ = new_player(client)

    res = client.post("/characters", json={}, headers={"Authorization": f"Bearer {user_id}"})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_api006_invalid_body_is_400(client):
    _, headers = new_player(client)

    res = client.post("/characters", json={"avatarId": 123}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api006_blank_avatar_id_is_400(client):
    _, headers = new_player(client)

    res = client.post("/characters", json={"avatarId": "   "}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api006_avatar_id_is_trimmed(client):
    _, headers = new_player(client)

    res = client.post("/characters", json={"avatarId": "  AVATAR_01 "}, headers=headers)

    assert res.status_code == 201
    assert res.json()["avatarId"] == "AVATAR_01"


def test_api006_docs_show_400_not_422(client):
    """입력 오류는 400으로 돌려주므로 Swagger에도 422가 없어야 한다."""
    responses = client.get("/openapi.json").json()["paths"]["/characters"]["post"]["responses"]

    assert "400" in responses
    assert "422" not in responses
