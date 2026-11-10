"""API-028 제출 상태 조회 — 노션 '전운시 API 명세서' API-028."""

import uuid
from datetime import UTC, datetime

from app.modules.submission.models import DailyCapReservation
from tests.character_helpers import new_player
from tests.submission_helpers import new_submission, prepare


def test_us01_api028_returns_submission_with_etag(client):
    submission_id, headers = new_submission(client, counted=30)

    res = client.get(f"/submissions/{submission_id}", headers=headers)

    assert res.status_code == 200
    assert res.headers["ETag"] == '"0"'
    body = res.json()
    assert set(body) == {
        "id", "sessionId", "exerciseCode", "status", "version", "approvalPath", "startedAt",
        "endedAt", "countedReps", "reservedReps", "confidence", "livenessPassed",
    }
    assert body["id"] == submission_id
    assert body["exerciseCode"] == "SQUAT"
    assert body["status"] == "SUBMITTED"
    assert body["version"] == 0
    assert body["approvalPath"] is None
    assert body["countedReps"] == 30
    assert body["reservedReps"] == 30
    assert body["confidence"] == 0.94
    # 무작위 동작 확인(API-021)을 하지 않은 세션은 null
    assert body["livenessPassed"] is None


def test_us01_api028_etag_follows_version(client):
    submission_id, headers = new_submission(client)
    prepare(client, submission_id)

    res = client.get(f"/submissions/{submission_id}", headers=headers)

    assert res.json()["status"] == "PREPARED"
    assert res.json()["version"] == 1
    assert res.headers["ETag"] == '"1"'


def test_us01_api028_released_reservation_shows_zero(client, db):
    submission_id, headers = new_submission(client)
    reservation = db.get(DailyCapReservation, uuid.UUID(submission_id))
    reservation.released_at = datetime.now(UTC)
    db.commit()

    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["reservedReps"] == 0


def test_us01_api028_other_user_is_403(client):
    submission_id, _ = new_submission(client)
    _, other = new_player(client)

    res = client.get(f"/submissions/{submission_id}", headers=other)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_us01_api028_unknown_is_404(client):
    _, headers = new_player(client)

    res = client.get(f"/submissions/{uuid.uuid4()}", headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_us01_api028_without_token_is_401(client):
    assert client.get(f"/submissions/{uuid.uuid4()}").status_code == 401
