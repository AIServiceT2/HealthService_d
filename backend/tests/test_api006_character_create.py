"""API-006 캐릭터 생성 — 노션 '전운시 API 명세서' API-006.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
인증은 임시: Bearer 토큰 값 = 사용자 UUID (app/modules/character/deps.py).
"""

import uuid


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_api006_create_character_returns_201_level1_exp0(client):
    user_id = uuid.uuid4()

    res = client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=_auth(user_id))

    assert res.status_code == 201
    assert res.json() == {"userId": str(user_id), "avatarId": "AVATAR_01", "exp": 0, "level": 1}


def test_api006_avatar_id_is_optional(client):
    user_id = uuid.uuid4()

    res = client.post("/characters", headers=_auth(user_id))

    assert res.status_code == 201
    assert res.json()["avatarId"] is None


def test_api006_second_character_for_same_user_is_409(client):
    user_id = uuid.uuid4()
    client.post("/characters", json={}, headers=_auth(user_id))

    res = client.post("/characters", json={"avatarId": "AVATAR_02"}, headers=_auth(user_id))

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_api006_other_user_can_create_own_character(client):
    client.post("/characters", json={}, headers=_auth(uuid.uuid4()))

    res = client.post("/characters", json={}, headers=_auth(uuid.uuid4()))

    assert res.status_code == 201


def test_api006_without_token_is_401(client):
    res = client.post("/characters", json={})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_api006_invalid_body_is_400(client):
    res = client.post("/characters", json={"avatarId": 123}, headers=_auth(uuid.uuid4()))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
