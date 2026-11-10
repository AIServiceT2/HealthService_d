"""API-030 승인 전 제출 취소 — 노션 '전운시 API 명세서' API-030, backlog US-06."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.submission_helpers import new_submission, prepare, start_session, submit, upload_chunks


def _cancel(client, submission_id, headers, version="0", body=None):
    return client.post(
        f"/submissions/{submission_id}/cancel",
        json=body if body is not None else {"reason": "자세가 이상해서 다시 하고 싶어요"},
        headers=headers | {"If-Match": f'"{version}"'},
    )


def _caps(client, headers):
    return client.get("/me/daily-caps", headers=headers).json()["items"][0]["reserved"]


def test_us06_cancel_submitted_releases_reservation(client):
    """(정상) SUBMITTED 건을 취소하면 CANCELED, 예약한 상한 인정량이 그만큼 줄어든다."""
    submission_id, headers = new_submission(client, counted=30)
    assert _caps(client, headers) == 30

    res = _cancel(client, submission_id, headers)

    assert res.status_code == 200
    assert res.json() == {"submissionId": submission_id, "status": "CANCELED", "releasedReps": 30, "version": 1}
    assert _caps(client, headers) == 0
    detail = client.get(f"/submissions/{submission_id}", headers=headers)
    assert detail.json()["status"] == "CANCELED"
    assert detail.json()["reservedReps"] == 0
    assert detail.headers["ETag"] == '"1"'


def test_us06_cancel_prepared_and_pending_review(client, db):
    submission_id, headers = new_submission(client)
    prepare(client, submission_id)  # version 1
    assert _cancel(client, submission_id, headers, version="1").json()["status"] == "CANCELED"

    other_id, other = new_submission(client)
    db.get(WorkoutSubmission, uuid.UUID(other_id)).status = "PENDING_REVIEW"
    db.commit()
    assert _cancel(client, other_id, other).status_code == 200


def test_us06_body_and_reason_are_optional(client):
    submission_id, headers = new_submission(client)

    res = client.post(f"/submissions/{submission_id}/cancel", headers=headers | {"If-Match": "0"})

    assert res.status_code == 200


def test_us06_approved_or_rewarded_is_409_and_unchanged(client, db):
    """(실패·거절) APPROVED·REWARDED 건의 취소 요청은 거부되고 상태가 바뀌지 않는다."""
    for status in ("APPROVED", "REWARDED"):
        submission_id, headers = new_submission(client)
        db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = status
        db.commit()

        res = _cancel(client, submission_id, headers)

        assert res.status_code == 409, status
        assert res.json()["code"] == "INVALID_STATE"
        assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == status
        assert _caps(client, headers) == 30


def test_us06_canceled_does_not_change_again(client):
    """(실패·거절) CANCELED 건은 다른 상태로 바뀌지 않는다: 다시 취소 409, 스냅샷 계산 409."""
    submission_id, headers = new_submission(client)
    _cancel(client, submission_id, headers)

    assert _cancel(client, submission_id, headers, version="1").status_code == 409
    assert prepare(client, submission_id).status_code == 409
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "CANCELED"


def test_us06_stale_version_is_412(client):
    """보상 계산(version 1) 뒤에 예전 version 0으로 취소하면 412, 상태는 그대로."""
    submission_id, headers = new_submission(client)
    prepare(client, submission_id)

    res = _cancel(client, submission_id, headers, version="0")

    assert res.status_code == 412
    assert res.json()["code"] == "CONCURRENT_UPDATE"
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "PREPARED"


def test_us06_concurrent_cancels_only_one_wins(client):
    """같은 version으로 동시에 와도 하나만 반영되고 나머지는 412 (backlog US-06 동시 요청)."""
    submission_id, headers = new_submission(client)

    def cancel(_):
        return _cancel(TestClient(app), submission_id, headers).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        codes = sorted(pool.map(cancel, range(5)))

    assert codes == [200, 412, 412, 412, 412]
    assert _caps(client, headers) == 0


def test_us06_only_applicant_can_cancel(client):
    """(권한) 신청자 본인만 취소할 수 있다."""
    submission_id, headers = new_submission(client)
    _, other = new_player(client)

    res = _cancel(client, submission_id, other)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "SUBMITTED"


def test_us06_unknown_is_404(client):
    _, headers = new_player(client)

    assert _cancel(client, uuid.uuid4(), headers).status_code == 404


def test_us06_if_match_required_and_valid(client):
    submission_id, headers = new_submission(client)
    url = f"/submissions/{submission_id}/cancel"

    assert client.post(url, json={}, headers=headers).status_code == 400
    assert client.post(url, json={}, headers=headers | {"If-Match": "abc"}).status_code == 400
    long_reason = {"reason": "가" * 201}
    assert client.post(url, json=long_reason, headers=headers | {"If-Match": "0"}).status_code == 400


def test_us06_after_cancel_same_time_can_be_submitted_again(client):
    """취소한 건은 시간대 중복 검사에서 빠져 새 세션으로 다시 제출할 수 있다."""
    _, headers = new_player(client)
    submission_id, _ = new_submission(client, headers=headers)
    _cancel(client, submission_id, headers)

    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id)

    assert submit(client, headers, session_id).status_code == 202


def test_us06_without_token_is_401(client):
    res = client.post(f"/submissions/{uuid.uuid4()}/cancel", json={}, headers={"If-Match": "0"})

    assert res.status_code == 401
