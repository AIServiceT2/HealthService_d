"""API-008 캐릭터 수정 — 노션 '전운시 API 명세서' API-008.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
수정 가능한 필드는 미정이라 avatarId만 받는다. 인증은 임시: Bearer 토큰 값 = 사용자 UUID.
"""

import uuid


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _create(client, user_id, avatar_id="AVATAR_01"):
    client.post("/characters", json={"avatarId": avatar_id}, headers=_auth(user_id))


def test_api008_update_avatar_returns_200(client):
    user_id = uuid.uuid4()
    _create(client, user_id)

    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=_auth(user_id))

    assert res.status_code == 200
    assert res.json() == {"userId": str(user_id), "avatarId": "AVATAR_02", "exp": 0, "level": 1}
    # 조회에도 반영된다
    assert client.get("/characters/me", headers=_auth(user_id)).json()["avatarId"] == "AVATAR_02"


def test_api008_empty_body_changes_nothing(client):
    user_id = uuid.uuid4()
    _create(client, user_id)

    res = client.patch("/characters/me", json={}, headers=_auth(user_id))

    assert res.status_code == 200
    assert res.json()["avatarId"] == "AVATAR_01"


def test_api008_only_own_character_is_updated(client):
    me, other = uuid.uuid4(), uuid.uuid4()
    _create(client, me)
    _create(client, other)

    client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=_auth(me))

    assert client.get("/characters/me", headers=_auth(other)).json()["avatarId"] == "AVATAR_01"


def test_api008_cannot_change_level_or_exp(client):
    user_id = uuid.uuid4()
    _create(client, user_id)

    res = client.patch("/characters/me", json={"level": 99, "exp": 9999}, headers=_auth(user_id))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
    body = client.get("/characters/me", headers=_auth(user_id)).json()
    assert body["level"] == 1
    assert body["exp"]["confirmed"] == 0


def test_api008_invalid_avatar_id_is_400(client):
    user_id = uuid.uuid4()
    _create(client, user_id)

    res = client.patch("/characters/me", json={"avatarId": 123}, headers=_auth(user_id))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_api008_without_character_is_404(client):
    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"}, headers=_auth(uuid.uuid4()))

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api008_without_token_is_401(client):
    res = client.patch("/characters/me", json={"avatarId": "AVATAR_02"})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
