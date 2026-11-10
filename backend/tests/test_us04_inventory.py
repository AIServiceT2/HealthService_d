"""API-044 인벤토리 조회 — 노션 '전운시 API 명세서' API-044, backlog US-04 (아이템 LOCKED 24시간)."""

import uuid
from datetime import datetime, timedelta

from app.modules.reward.models import RewardLedger
from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.reward_helpers import approved_submission, grant
from tests.submission_helpers import TEST_INTERNAL_TOKEN


def _rewarded(client, db, headers=None, hours_ago=0):
    submission_id, headers = approved_submission(client, db, headers=headers)
    grant(client, submission_id)
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.ended_at = saved.started_at  # 다음 제출과 시간대가 겹치지 않게
    db.get(RewardLedger, uuid.UUID(submission_id)).rewarded_at -= timedelta(hours=hours_ago)
    db.commit()
    return submission_id, headers


def test_us04_inventory_lists_my_items_with_unlock_time(client, db):
    old_id, headers = _rewarded(client, db, hours_ago=30)
    new_id, _ = _rewarded(client, db, headers=headers, hours_ago=1)
    _rewarded(client, db)  # 다른 사용자 아이템은 나오지 않는다
    client.post("/internal/reward-locks/release", headers={"X-Internal-Token": TEST_INTERNAL_TOKEN})

    res = client.get("/me/inventory", headers=headers)

    assert res.status_code == 200
    items = res.json()["items"]
    assert [(i["submissionId"], i["status"]) for i in items] == [(new_id, "LOCKED"), (old_id, "UNLOCKED")]
    assert set(items[0]) == {"itemId", "submissionId", "status", "unlockAt"}
    rewarded_at = db.get(RewardLedger, uuid.UUID(new_id)).rewarded_at
    assert datetime.fromisoformat(items[0]["unlockAt"]) == rewarded_at + timedelta(hours=24)
    # 지급 결과(API-041)의 아이템 ID와 같다
    granted = client.get("/me/rewards", headers=headers).json()["items"][0]["items"][0]["itemId"]
    assert items[0]["itemId"] == granted


def test_us04_inventory_empty(client):
    _, headers = new_player(client)

    assert client.get("/me/inventory", headers=headers).json() == {"items": []}


def test_us04_inventory_no_items_when_no_drop(client, db):
    """상한 초과로 0타면 드랍도 0이라 아이템이 생기지 않는다."""
    from app.modules.submission.models import DailyCapReservation
    from tests.submission_helpers import new_submission, prepare

    submission_id, headers = new_submission(client)
    client.post("/characters", json={}, headers=headers)
    db.get(DailyCapReservation, uuid.UUID(submission_id)).amount = 0
    db.commit()
    prepare(client, submission_id)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "APPROVED"
    db.commit()
    assert grant(client, submission_id).json()["applied"]["items"] == []

    assert client.get("/me/inventory", headers=headers).json() == {"items": []}


def test_us04_inventory_without_token_is_401(client):
    res = client.get("/me/inventory")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
