"""운동 세션 API 테스트 — 노션 '전운시 API 명세서' API-018~025 (US-01 운동하면 렙을 세어 자동 제출의 앞단).

로그인은 실제 회원 가입·로그인으로 받은 access token을 쓴다 (tests/character_helpers.py).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from tests.character_helpers import new_player

# ---- API-018 운동 목록·판정 기준·튜토리얼 ----


def test_us01_api018_lists_squat_only(client):
    _, headers = new_player(client)

    res = client.get("/exercises", headers=headers)

    assert res.status_code == 200
    assert res.json() == {
        "catalogVersion": "cat_2026-11-01",
        "items": [
            {
                "code": "SQUAT",
                "name": "스쿼트",
                "dailyCap": 200,
                "criteria": {"kneeAngleMax": None},
                "recommendedCameraAngle": None,
                "tutorialUrl": None,
            }
        ],
    }


def test_us01_api018_requires_login(client):
    res = client.get("/exercises")
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


# ---- API-019 내 일일 상한 조회 ----


def test_us01_api019_returns_today_kst_caps(client):
    _, headers = new_player(client)

    res = client.get("/me/daily-caps", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["date"] == datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    # 제출(API-026)이 없어 예약 0 → 상한 200이 그대로 남음
    assert body["items"] == [{"exerciseCode": "SQUAT", "cap": 200, "reserved": 0, "remaining": 200}]


def test_us01_api019_requires_login(client):
    assert client.get("/me/daily-caps").status_code == 401
