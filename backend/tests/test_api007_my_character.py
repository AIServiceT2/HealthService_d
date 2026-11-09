"""API-007 내 캐릭터·성장 조회 — 노션 '전운시 API 명세서' API-007.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
인증은 임시: Bearer 토큰 값 = 사용자 UUID (app/modules/character/deps.py).
"""

import uuid


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_api007_returns_my_character_growth(client):
    user_id = uuid.uuid4()
    client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=_auth(user_id))

    res = client.get("/characters/me", headers=_auth(user_id))

    assert res.status_code == 200
    # level·exp.pending·lockedItemCount는 의존 기능이 없어 생성 직후 값 (service.py 참고)
    assert res.json() == {
        "userId": str(user_id),
        "avatarId": "AVATAR_01",
        "level": 1,
        "exp": {"confirmed": 0, "pending": 0},
        "stats": [],
        "lockedItemCount": 0,
    }


def test_api007_returns_only_own_character(client):
    me, other = uuid.uuid4(), uuid.uuid4()
    client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=_auth(me))
    client.post("/characters", json={"avatarId": "AVATAR_02"}, headers=_auth(other))

    res = client.get("/characters/me", headers=_auth(me))

    assert res.json()["userId"] == str(me)
    assert res.json()["avatarId"] == "AVATAR_01"


def test_api007_without_character_is_404(client):
    res = client.get("/characters/me", headers=_auth(uuid.uuid4()))

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api007_without_token_is_401(client):
    res = client.get("/characters/me")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
