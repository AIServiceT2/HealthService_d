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
