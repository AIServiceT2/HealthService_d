"""API-009 길드 생성 — 노션 '전운시 API 명세서' API-009.

길드는 US 번호가 없는 F-01(US-07 전제, 노션 기능명세 JN-011)이라 테스트 이름에 API ID를 쓴다
(CODE-STYLE 6번과 다름, 팀 확인 필요). 로그인은 실제 회원 가입·로그인으로 받은 access token.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from tests.character_helpers import new_player


def test_api009_create_guild_returns_201_and_creator_is_leader(client):
    user_id, headers = new_player(client)

    res = client.post("/guilds", json={"name": "부산 스쿼터즈"}, headers=headers)

    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"guildId", "name", "leaderUserId"}
    assert body["name"] == "부산 스쿼터즈"
    assert body["leaderUserId"] == str(user_id)


def test_api009_creator_becomes_member(client):
    _, headers = new_player(client)

    guild_id = client.post("/guilds", json={"name": "부산 스쿼터즈"}, headers=headers).json()["guildId"]

    # 소속 길드가 생겨서 다른 길드를 또 만들 수 없다 (409)
    again = client.post("/guilds", json={"name": "다른 길드"}, headers=headers)
    assert again.status_code == 409
    assert again.json()["code"] == "INVALID_STATE"
    assert guild_id


def test_api009_name_is_trimmed(client):
    _, headers = new_player(client)

    res = client.post("/guilds", json={"name": "  부산 스쿼터즈 "}, headers=headers)

    assert res.status_code == 201
    assert res.json()["name"] == "부산 스쿼터즈"


def test_api009_name_length_2_and_20_are_ok(client):
    _, a = new_player(client)
    _, b = new_player(client)

    assert client.post("/guilds", json={"name": "가나"}, headers=a).status_code == 201
    assert client.post("/guilds", json={"name": "가" * 20}, headers=b).status_code == 201


def test_api009_invalid_name_is_400(client):
    _, headers = new_player(client)

    for bad in [{"name": "가"}, {"name": "가" * 21}, {"name": "   "}, {"name": 123}, {}]:
        res = client.post("/guilds", json=bad, headers=headers)
        assert res.status_code == 400, bad
        assert res.json()["code"] == "VALIDATION_FAILED"

    # 실패한 요청으로 길드가 생기지 않았다
    assert client.post("/guilds", json={"name": "부산 스쿼터즈"}, headers=headers).status_code == 201


def test_api009_same_name_is_allowed_for_different_users(client):
    """명세에 이름 중복 제한이 없다."""
    _, a = new_player(client)
    _, b = new_player(client)

    assert client.post("/guilds", json={"name": "부산 스쿼터즈"}, headers=a).status_code == 201
    assert client.post("/guilds", json={"name": "부산 스쿼터즈"}, headers=b).status_code == 201


def test_api009_concurrent_create_by_same_user_makes_one_guild(client):
    _, headers = new_player(client)

    def create(i):
        return TestClient(app).post("/guilds", json={"name": f"길드{i}"}, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(create, range(6)))

    assert sorted(codes) == [201] + [409] * 5


def test_api009_without_token_is_401(client):
    res = client.post("/guilds", json={"name": "부산 스쿼터즈"})

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_api009_docs_show_400_not_422(client):
    responses = client.get("/openapi.json").json()["paths"]["/guilds"]["post"]["responses"]

    assert "400" in responses
    assert "422" not in responses


def test_api009_docs_error_details_allow_list(client):
    """입력 오류의 details는 목록으로 오므로 문서의 에러 본문도 목록을 허용해야 한다."""
    _, headers = new_player(client)
    res = client.post("/guilds", json={"name": "가"}, headers=headers)
    assert isinstance(res.json()["details"], list)

    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    details = schemas["ErrorResponse"]["properties"]["details"]
    allowed = {option.get("type") for option in details["anyOf"]}
    assert {"object", "array", "null"} <= allowed
