"""회원 가입 성별(선택) — 시안 '성별 (가입 단계)', 2026-11-11 팀 요청으로 API-001에 더한 필드.

노션 명세에 없는 [추가] 필드라 테스트 이름에 f01과 API ID를 쓴다 (test_f01_auth.py와 같은 방식).
"""

import uuid

from app.modules.auth.models import User

SIGNUP = {
    "provider": "EMAIL",
    "email": "gender@example.com",
    "password": "example-password",
    "nickname": "민규",
    "birthDate": "2010-03-14",
}


def test_f01_api001_gender_is_saved(client, db):
    for i, gender in enumerate(["MALE", "FEMALE"]):
        res = client.post("/auth/signup", json={**SIGNUP, "email": f"g{i}@example.com", "gender": gender})
        assert res.status_code == 201
        assert db.get(User, uuid.UUID(res.json()["userId"])).gender == gender


def test_f01_api001_gender_is_optional(client, db):
    """선택하지 않아도(필드 없음·null) 가입할 수 있다."""
    without = client.post("/auth/signup", json=SIGNUP)
    with_null = client.post("/auth/signup", json={**SIGNUP, "email": "null@example.com", "gender": None})

    for res in (without, with_null):
        assert res.status_code == 201
        assert db.get(User, uuid.UUID(res.json()["userId"])).gender is None


def test_f01_api001_unknown_gender_is_400(client):
    res = client.post("/auth/signup", json={**SIGNUP, "gender": "OTHER"})

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
