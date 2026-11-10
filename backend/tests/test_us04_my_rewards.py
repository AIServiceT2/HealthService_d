"""API-043 내 지급 내역 — 노션 '전운시 API 명세서' API-043, backlog US-04 (권한: 남의 지급 내역은 볼 수 없다)."""

import uuid
from datetime import datetime, timedelta

from app.modules.reward.models import RewardLedger
from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.reward_helpers import approved_submission, grant


def _rewarded(client, db, headers=None, hours_ago=0):
    """지급까지 마친 제출건. 같은 사용자 건을 여러 개 만들면 시간대가 겹치지 않게 시각을 옮긴다."""
    submission_id, headers = approved_submission(client, db, headers=headers)
    grant(client, submission_id)
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.ended_at = saved.started_at  # 다음 제출과 시간대가 겹치지 않게
    db.get(RewardLedger, uuid.UUID(submission_id)).rewarded_at -= timedelta(hours=hours_ago)
    db.commit()
    return submission_id, headers


def test_us04_my_rewards_lists_latest_first(client, db):
    old_id, headers = _rewarded(client, db, hours_ago=30)
    new_id, _ = _rewarded(client, db, headers=headers, hours_ago=1)
    _rewarded(client, db)  # 다른 사용자 지급은 나오지 않는다

    res = client.get("/me/rewards", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert [i["submissionId"] for i in body["items"]] == [new_id, old_id]
    assert body["nextCursor"] is None
    first = body["items"][0]
    assert set(first) == {"submissionId", "exp", "items", "damage", "rewardedAt", "protectionEndsAt"}
    assert first["exp"] == 150
    assert first["damage"] == 900
    assert [i["status"] for i in first["items"]] == ["LOCKED"]
    rewarded_at = datetime.fromisoformat(first["rewardedAt"])
    assert datetime.fromisoformat(first["protectionEndsAt"]) == rewarded_at + timedelta(hours=24)


def test_us04_my_rewards_shows_unlocked_after_release(client, db):
    from tests.submission_helpers import TEST_INTERNAL_TOKEN

    _, headers = _rewarded(client, db, hours_ago=25)
    client.post("/internal/reward-locks/release", headers={"X-Internal-Token": TEST_INTERNAL_TOKEN})

    items = client.get("/me/rewards", headers=headers).json()["items"][0]["items"]

    assert [i["status"] for i in items] == ["UNLOCKED"]


def test_us04_my_rewards_pages_with_cursor(client, db):
    _, headers = _rewarded(client, db, hours_ago=1)
    for hours in (2, 3, 4):
        _rewarded(client, db, headers=headers, hours_ago=hours)
    expected = [i["submissionId"] for i in client.get("/me/rewards", headers=headers).json()["items"]]

    seen, cursor = [], None
    for _ in range(4):
        params = {"limit": 3} | ({"cursor": cursor} if cursor else {})
        body = client.get("/me/rewards", params=params, headers=headers).json()
        seen += [i["submissionId"] for i in body["items"]]
        cursor = body["nextCursor"]
        if cursor is None:
            break

    assert seen == expected
    assert len(seen) == 4


def test_us04_my_rewards_empty_and_not_yet_rewarded(client, db):
    """지급 전(APPROVED) 건은 지급 내역에 없다."""
    _, headers = approved_submission(client, db)

    assert client.get("/me/rewards", headers=headers).json() == {"items": [], "nextCursor": None}


def test_us04_my_rewards_invalid_query_is_400(client):
    _, headers = new_player(client)

    for params in ({"limit": 0}, {"limit": 51}, {"cursor": "broken"}):
        res = client.get("/me/rewards", params=params, headers=headers)
        assert res.status_code == 400, params
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_us04_my_rewards_without_token_is_401(client):
    res = client.get("/me/rewards")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
