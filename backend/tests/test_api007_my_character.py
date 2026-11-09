"""API-007 내 캐릭터·성장 조회 — 노션 '전운시 API 명세서' API-007.

캐릭터는 US 번호가 없는 F-01(US-01~05의 전제)이라 테스트 이름에 API ID를 쓴다 (CODE-STYLE 6번과 다름, 팀 확인 필요).
로그인은 실제 회원 가입·로그인으로 받은 access token을 쓴다 (tests/character_helpers.py).
"""

from tests.character_helpers import new_player


def test_api007_returns_my_character_growth(client):
    user_id, headers = new_player(client)
    client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=headers)

    res = client.get("/characters/me", headers=headers)

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
    me, my_headers = new_player(client)
    _, other_headers = new_player(client)
    client.post("/characters", json={"avatarId": "AVATAR_01"}, headers=my_headers)
    client.post("/characters", json={"avatarId": "AVATAR_02"}, headers=other_headers)

    res = client.get("/characters/me", headers=my_headers)

    assert res.json()["userId"] == str(me)
    assert res.json()["avatarId"] == "AVATAR_01"


def test_api007_without_character_is_404(client):
    _, headers = new_player(client)

    res = client.get("/characters/me", headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_api007_without_token_is_401(client):
    res = client.get("/characters/me")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
