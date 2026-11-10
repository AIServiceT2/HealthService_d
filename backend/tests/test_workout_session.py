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


# ---- API-020 운동 세션 시작 ----

START_BODY = {
    "exerciseCode": "SQUAT",
    "goal": {"reps": 30, "sets": 1},
    "target": {"type": "DUNGEON", "id": "6f1c2b1e-8a1d-4b8e-9a51-0d6c1f7f2a10"},
    "device": {"os": "android", "model": "SM-S921N"},
}


def start_session(client, headers, body=START_BODY):
    res = client.post("/workout-sessions", json=body, headers=headers)
    assert res.status_code == 201, res.json()
    return res.json()


def test_us01_api020_starts_active_session_with_liveness_challenge(client):
    _, headers = new_player(client)

    body = start_session(client, headers)

    assert body["status"] == "ACTIVE"
    assert body["catalogVersion"] == "cat_2026-11-01"
    assert body["remainingDailyCap"] == 200
    assert body["liveness"]["action"] in {"RAISE_LEFT_HAND", "RAISE_RIGHT_HAND", "RAISE_BOTH_HANDS"}
    assert body["liveness"]["timeoutSec"] == 10
    assert body["chunkSpec"] == {"maxFrames": 300, "maxBytes": 262144}
    assert {"sessionId", "liveness"} <= body.keys()
    assert "challengeId" in body["liveness"]


def test_us01_api020_goal_target_device_are_optional(client):
    _, headers = new_player(client)
    start_session(client, headers, {"exerciseCode": "SQUAT"})


def test_us01_api020_rejects_unknown_exercise(client):
    _, headers = new_player(client)

    res = client.post("/workout-sessions", json={**START_BODY, "exerciseCode": "PUSHUP"}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_us01_api020_rejects_bad_goal_and_target(client):
    _, headers = new_player(client)
    bad_goal = {**START_BODY, "goal": {"reps": 0, "sets": 1}}
    bad_target = {**START_BODY, "target": {"type": "RAID", "id": START_BODY["target"]["id"]}}

    assert client.post("/workout-sessions", json=bad_goal, headers=headers).status_code == 400
    assert client.post("/workout-sessions", json=bad_target, headers=headers).status_code == 400


def test_us01_api020_requires_login(client):
    assert client.post("/workout-sessions", json=START_BODY).status_code == 401
