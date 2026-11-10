"""API-033 자동 승인 판정 — backlog US-03 AI 확신도 기준 이상이면 바로 승인."""

from tests.review_helpers import auto_approval, new_prepared, version_of
from tests.submission_helpers import new_submission


def test_us03_api033_approves_when_confidence_and_liveness_pass(client):
    sid, headers = new_prepared(client, confidence=0.94, liveness=True)
    before = version_of(client, sid, headers)

    res = auto_approval(client, sid)

    assert res.status_code == 200
    assert res.json() == {
        "decision": "AUTO_APPROVED",
        "confidence": 0.94,
        "threshold": 0.9,
        "livenessPassed": True,
        "submissionStatus": "APPROVED",
        "approvalPath": "AI_AUTO",
    }
    detail = client.get(f"/submissions/{sid}", headers=headers).json()
    assert detail["status"] == "APPROVED"
    assert detail["approvalPath"] == "AI_AUTO"
    assert detail["version"] == before + 1


def test_us03_api033_threshold_is_inclusive(client):
    sid, _ = new_prepared(client, confidence=0.90, liveness=True)
    assert auto_approval(client, sid).json()["decision"] == "AUTO_APPROVED"


def test_us03_api033_low_confidence_stays_prepared(client):
    sid, headers = new_prepared(client, confidence=0.82, liveness=True)
    before = version_of(client, sid, headers)

    res = auto_approval(client, sid)

    assert res.status_code == 200
    assert res.json()["decision"] == "NEEDS_REVIEW"
    assert res.json()["submissionStatus"] == "PREPARED"
    assert res.json()["approvalPath"] is None
    assert version_of(client, sid, headers) == before


def test_us03_api033_without_liveness_is_not_auto_approved_regardless_of_confidence(client):
    sid, _ = new_prepared(client, confidence=0.99, liveness=False)

    res = auto_approval(client, sid)

    assert res.json()["decision"] == "NEEDS_REVIEW"
    assert res.json()["livenessPassed"] is None
    assert res.json()["submissionStatus"] == "PREPARED"


def test_us03_api033_rejects_submitted_skipping_prepared(client):
    sid, _ = new_submission(client)  # SUBMITTED (스냅샷 전)

    res = auto_approval(client, sid)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us03_api033_canceled_first_is_412(client):
    sid, headers = new_prepared(client)
    version = version_of(client, sid, headers)
    assert client.post(f"/submissions/{sid}/cancel", headers=headers | {"If-Match": f'"{version}"'}).status_code == 200

    res = auto_approval(client, sid)

    assert res.status_code == 412
    assert res.json()["code"] == "CONCURRENT_UPDATE"


def test_us03_api033_already_approved_is_409(client):
    sid, _ = new_prepared(client)
    auto_approval(client, sid)

    assert auto_approval(client, sid).status_code == 409


def test_us03_api033_internal_only(client):
    sid, headers = new_prepared(client)

    no_token = client.post(f"/internal/submissions/{sid}/auto-approval")
    as_player = client.post(f"/internal/submissions/{sid}/auto-approval", headers=headers)

    assert no_token.status_code == 401
    assert as_player.status_code == 401


def test_us03_api033_missing_submission_is_404(client):
    assert auto_approval(client, "00000000-0000-0000-0000-000000000000").status_code == 404
