"""API-031 보상 스냅샷 계산·고정 — 노션 '전운시 API 명세서' API-031 (US-02).

exp·피해·드랍은 명세 예시 비율의 가안 (app/modules/snapshot/rules.py).
"""

import uuid

from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.models import DailyCapReservation, WorkoutSubmission
from tests.submission_helpers import internal_headers, new_submission, prepare


def test_us02_api031_fixes_snapshot_and_moves_to_prepared(client, db):
    submission_id, _ = new_submission(client, counted=30)

    res = prepare(client, submission_id)

    assert res.status_code == 200
    assert res.json() == {
        "submissionId": submission_id,
        "catalogVersion": "cat_2026-11-01",
        "hitCount": 30,
        "exp": 150,
        "totalDamage": 900,
        "weaknessMultiplier": 1.0,
        "dropCount": 1,
    }
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    assert saved.status == "PREPARED"
    assert saved.version == 1


def test_us02_api031_repeat_returns_same_snapshot(client, db):
    submission_id, _ = new_submission(client)
    first = prepare(client, submission_id)

    again = prepare(client, submission_id)

    assert again.status_code == 200
    assert again.json() == first.json()
    assert db.get(WorkoutSubmission, uuid.UUID(submission_id)).version == 1


def test_us02_api031_snapshot_does_not_change_after_rules_change(client, monkeypatch):
    """카탈로그(규칙)가 바뀌어도 이미 고정한 수치는 그대로 (backlog US-02 #2)."""
    from app.modules.snapshot import rules

    submission_id, _ = new_submission(client)
    first = prepare(client, submission_id).json()
    monkeypatch.setattr(rules, "EXP_PER_HIT", 999)

    assert prepare(client, submission_id).json() == first


def test_us01_api031_over_daily_cap_gives_zero_hits(client, db):
    """그날 상한을 넘어 보상 대상 인정량이 0이면 타격 0·드랍 0 (backlog US-01·05)."""
    submission_id, _ = new_submission(client)
    db.get(DailyCapReservation, uuid.UUID(submission_id)).amount = 0
    db.commit()

    body = prepare(client, submission_id).json()

    assert body["hitCount"] == 0
    assert body["exp"] == 0
    assert body["totalDamage"] == 0
    assert body["dropCount"] == 0


def test_us02_api031_not_submitted_is_409(client, db):
    submission_id, _ = new_submission(client)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "CANCELED"
    db.commit()

    res = prepare(client, submission_id)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"
    assert db.get(SubmissionSnapshot, uuid.UUID(submission_id)) is None


def test_us02_api031_unknown_submission_is_404(client):
    assert prepare(client, str(uuid.uuid4())).status_code == 404


def test_us02_api031_internal_only(client):
    """플레이어 토큰이나 잘못된 내부 토큰으로는 부를 수 없다 (권한 SYSTEM)."""
    submission_id, player = new_submission(client)
    url = f"/internal/submissions/{submission_id}/snapshot"
    key = {"Idempotency-Key": str(uuid.uuid4())}

    for headers in (key, player | key, key | {"X-Internal-Token": "wrong"}):
        res = client.post(url, headers=headers)
        assert res.status_code == 401
        assert res.json()["code"] == "UNAUTHENTICATED"


def test_us02_api031_no_internal_token_configured_is_401(client, monkeypatch):
    monkeypatch.delenv("INTERNAL_API_TOKEN")
    submission_id, _ = new_submission(client)

    res = client.post(f"/internal/submissions/{submission_id}/snapshot", headers=internal_headers())

    assert res.status_code == 401


def test_us02_api031_requires_idempotency_key(client):
    submission_id, _ = new_submission(client)
    headers = {"X-Internal-Token": internal_headers()["X-Internal-Token"]}

    res = client.post(f"/internal/submissions/{submission_id}/snapshot", headers=headers)

    assert res.status_code == 400
