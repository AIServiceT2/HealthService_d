"""F-01 회원·로그인 (노션 API 명세서 API-001~005).

F-01은 연결된 US가 없어(PRD 3절 'US-01~05의 전제') 테스트 이름에 US 대신 f01과 API ID를 쓴다.
기대값은 노션 각 API 페이지의 RESPONSE·Error Code에서 가져온다.
"""

import uuid
from datetime import date

SIGNUP = {
    "provider": "EMAIL",
    "email": "user@example.com",
    "password": "example-password",
    "nickname": "민규",
    "birthDate": "2010-03-14",
}


def _years_ago(years: int, days_offset: int = 0) -> str:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    try:
        d = today.replace(year=today.year - years)
    except ValueError:  # 2월 29일
        d = date(today.year - years, 2, 28)
    return (d + timedelta(days=days_offset)).isoformat()


def _signup(client, **overrides):
    return client.post("/auth/signup", json={**SIGNUP, **overrides})


# ---- API-001 회원 가입 ----


def test_f01_api001_signup_returns_201_and_user_id(client):
    res = _signup(client)
    assert res.status_code == 201
    assert uuid.UUID(res.json()["userId"])


def test_f01_api001_duplicate_email_is_400(client):
    assert _signup(client).status_code == 201
    res = _signup(client, email="USER@example.com", nickname="다른사람")
    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_f01_api001_under_14_is_400_and_exactly_14_is_201(client):
    under = _signup(client, birthDate=_years_ago(14, days_offset=1))
    assert under.status_code == 400
    assert under.json()["code"] == "VALIDATION_FAILED"

    exact = _signup(client, email="fourteen@example.com", birthDate=_years_ago(14))
    assert exact.status_code == 201


def test_f01_api001_invalid_fields_are_400(client):
    cases = [
        {"provider": "KAKAO"},
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 65},
        {"nickname": "a"},
        {"nickname": "x" * 13},
    ]
    for override in cases:
        res = _signup(client, **override)
        assert res.status_code == 400, override
        body = res.json()
        assert body["code"] == "VALIDATION_FAILED"
        assert set(body) == {"code", "message", "details"}


def test_f01_api001_password_is_not_stored_in_plain_text(client, db):
    from app.modules.auth.models import User

    user_id = _signup(client).json()["userId"]
    user = db.get(User, uuid.UUID(user_id))
    assert user.password_hash != SIGNUP["password"]
    assert SIGNUP["password"] not in user.password_hash


# ---- API-002 로그인 ----

LOGIN = {"provider": "EMAIL", "email": SIGNUP["email"], "password": SIGNUP["password"]}


def _login(client, **overrides):
    return client.post("/auth/login", json={**LOGIN, **overrides})


def test_f01_api002_login_returns_tokens_and_user(client):
    user_id = _signup(client).json()["userId"]

    res = _login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["accessToken"]
    assert body["accessTokenExpiresIn"] == 1800
    assert body["refreshToken"]
    assert body["user"] == {"id": user_id, "nickname": "민규", "guildId": None}


def test_f01_api002_wrong_password_or_unknown_email_is_401(client):
    _signup(client)
    for override in ({"password": "wrong-password"}, {"email": "nobody@example.com"}):
        res = _login(client, **override)
        assert res.status_code == 401, override
        assert res.json()["code"] == "UNAUTHENTICATED"


def test_f01_api002_invalid_body_is_400(client):
    res = client.post("/auth/login", json={"provider": "EMAIL", "email": SIGNUP["email"]})
    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_f01_api002_refresh_token_is_stored_only_as_hash(client, db):
    from sqlalchemy import select

    from app.modules.auth.models import RefreshToken

    _signup(client)
    refresh = _login(client).json()["refreshToken"]
    stored = db.scalars(select(RefreshToken.token_hash)).all()
    assert len(stored) == 1
    assert refresh not in stored


# ---- API-003 토큰 재발급 ----


def _refresh(client, token):
    return client.post("/auth/refresh", json={"refreshToken": token})


def test_f01_api003_refresh_issues_new_tokens(client):
    _signup(client)
    old = _login(client).json()["refreshToken"]

    res = _refresh(client, old)
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"accessToken", "accessTokenExpiresIn", "refreshToken"}
    assert body["accessTokenExpiresIn"] == 1800
    assert body["refreshToken"] != old


def test_f01_api003_old_refresh_token_is_revoked_after_rotation(client):
    _signup(client)
    old = _login(client).json()["refreshToken"]
    new = _refresh(client, old).json()["refreshToken"]

    reused = _refresh(client, old)
    assert reused.status_code == 401
    assert reused.json()["code"] == "UNAUTHENTICATED"
    assert _refresh(client, new).status_code == 200


def test_f01_api003_unknown_or_expired_refresh_token_is_401(client, db):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.modules.auth.models import RefreshToken

    assert _refresh(client, "not-a-real-token").status_code == 401

    _signup(client)
    token = _login(client).json()["refreshToken"]
    db.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    res = _refresh(client, token)
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_f01_api003_same_refresh_token_twice_at_once_succeeds_only_once(client):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    from app.main import app

    _signup(client)
    token = _login(client).json()["refreshToken"]

    def call(_):
        return TestClient(app).post("/auth/refresh", json={"refreshToken": token}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(call, range(2)))
    assert codes == [200, 401]


# ---- API-004 로그아웃 ----


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_f01_api004_logout_revokes_refresh_token(client):
    _signup(client)
    tokens = _login(client).json()

    res = client.post(
        "/auth/logout",
        json={"refreshToken": tokens["refreshToken"]},
        headers=_bearer(tokens["accessToken"]),
    )
    assert res.status_code == 204
    assert res.content == b""
    assert _refresh(client, tokens["refreshToken"]).status_code == 401


def test_f01_api004_logout_without_or_with_bad_bearer_is_401(client):
    _signup(client)
    tokens = _login(client).json()
    body = {"refreshToken": tokens["refreshToken"]}

    for headers in ({}, _bearer("not-a-jwt"), _bearer(tokens["refreshToken"])):
        res = client.post("/auth/logout", json=body, headers=headers)
        assert res.status_code == 401, headers
        assert res.json()["code"] == "UNAUTHENTICATED"
    # 거부된 요청은 refresh 토큰을 폐기하지 않는다
    assert _refresh(client, tokens["refreshToken"]).status_code == 200


def test_f01_api004_expired_access_token_is_401(client):
    from datetime import UTC, datetime, timedelta

    from app.modules.auth.service import create_access_token

    user_id = uuid.UUID(_signup(client).json()["userId"])
    expired = create_access_token(user_id, now=datetime.now(UTC) - timedelta(hours=1))
    res = client.post("/auth/logout", json={"refreshToken": "x"}, headers=_bearer(expired))
    assert res.status_code == 401


def test_f01_api004_cannot_revoke_other_users_refresh_token(client):
    _signup(client)
    victim = _login(client).json()
    _signup(client, email="other@example.com", nickname="다른사람")
    attacker = _login(client, email="other@example.com").json()

    res = client.post(
        "/auth/logout",
        json={"refreshToken": victim["refreshToken"]},
        headers=_bearer(attacker["accessToken"]),
    )
    assert res.status_code == 204
    assert _refresh(client, victim["refreshToken"]).status_code == 200
