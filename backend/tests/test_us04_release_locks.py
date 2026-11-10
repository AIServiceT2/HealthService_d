"""API-042 24시간 잠금 해제·능력치 확정 (배치) — 노션 '전운시 API 명세서' API-042, backlog US-04.

해제 뒤 상태명 UNLOCKED와 '24시간 정각부터 해제'는 제안값. 능력치 확정은 모델이 없어 0.
"""

import uuid
from datetime import timedelta

from app.modules.reward.models import Item, RewardLedger
from tests.reward_helpers import approved_submission, grant
from tests.submission_helpers import TEST_INTERNAL_TOKEN


def _release(client, now=None, headers=None):
    body = {"now": now.isoformat()} if now else None
    return client.post(
        "/internal/reward-locks/release",
        json=body,
        headers=headers if headers is not None else {"X-Internal-Token": TEST_INTERNAL_TOKEN},
    )


def _granted(client, db):
    submission_id, headers = approved_submission(client, db)
    grant(client, submission_id)
    rewarded_at = db.get(RewardLedger, uuid.UUID(submission_id)).rewarded_at
    return submission_id, headers, rewarded_at


def _statuses(db):
    db.expire_all()
    return [i.status for i in db.query(Item).all()]


def test_us04_release_before_24h_keeps_locked(client, db):
    _, headers, rewarded_at = _granted(client, db)

    res = _release(client, rewarded_at + timedelta(hours=23, minutes=59))

    assert res.status_code == 200
    assert res.json() == {"releasedItems": 0, "confirmedStats": 0}
    assert _statuses(db) == ["LOCKED"]
    assert client.get("/characters/me", headers=headers).json()["lockedItemCount"] == 1


def test_us04_release_at_24h_unlocks(client, db):
    """24시간 정각부터 해제 (제안). 다시 돌려도 이미 푼 아이템은 세지 않는다."""
    _, headers, rewarded_at = _granted(client, db)

    res = _release(client, rewarded_at + timedelta(hours=24))

    assert res.json() == {"releasedItems": 1, "confirmedStats": 0}
    assert _statuses(db) == ["UNLOCKED"]
    assert client.get("/characters/me", headers=headers).json()["lockedItemCount"] == 0
    assert _release(client, rewarded_at + timedelta(hours=25)).json()["releasedItems"] == 0


def test_us04_release_only_old_rewards(client, db):
    old_id, _, old_at = _granted(client, db)
    new_id, _, _ = _granted(client, db)
    db.get(RewardLedger, uuid.UUID(new_id)).rewarded_at = old_at + timedelta(hours=12)
    db.commit()

    res = _release(client, old_at + timedelta(hours=24))

    assert res.json()["releasedItems"] == 1
    db.expire_all()
    by_submission = {str(i.submission_id): i.status for i in db.query(Item).all()}
    assert by_submission == {old_id: "UNLOCKED", new_id: "LOCKED"}


def test_us04_release_without_body_uses_server_time(client, db):
    submission_id, _, rewarded_at = _granted(client, db)
    db.get(RewardLedger, uuid.UUID(submission_id)).rewarded_at = rewarded_at - timedelta(hours=25)
    db.commit()

    res = _release(client)

    assert res.json()["releasedItems"] == 1


def test_us04_release_is_internal_only(client, db):
    _, player, _ = _granted(client, db)

    for headers in ({}, player, {"X-Internal-Token": "wrong"}):
        assert _release(client, headers=headers).status_code == 401
    assert _statuses(db) == ["LOCKED"]


def test_us04_release_invalid_now_is_400(client):
    res = client.post(
        "/internal/reward-locks/release",
        json={"now": "2026-11-10T05:15:00"},  # 시간대 없음
        headers={"X-Internal-Token": TEST_INTERNAL_TOKEN},
    )

    assert res.status_code == 400
