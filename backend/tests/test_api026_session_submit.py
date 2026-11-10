"""API-026 세션 종료·운동 제출 — 노션 '전운시 API 명세서' API-026 (US-01 운동하면 렙을 세어 자동 제출).

서버 재계산은 ai/ 엔진 연결 전이라 앱이 보낸 reps 중 counted=true 수를 쓴다 (service.recount_reps, 임시).
"""

import uuid

from app.modules.submission.models import DailyCapReservation, RepEvent, WorkoutSubmission
from tests.character_helpers import new_player
from tests.submission_helpers import start_session, submit, submit_body, upload_chunks


def _ready_session(client, chunks=1):
    _, headers = new_player(client)
    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id, chunks)
    return session_id, headers


def test_us01_api026_submit_creates_submitted_with_counted_reps(client, db):
    session_id, headers = _ready_session(client, chunks=2)

    res = submit(client, headers, session_id, submit_body(counted=30, uncounted=2, chunks=2))

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "SUBMITTED"
    assert body["countedReps"] == 30
    assert body["reservedReps"] == 30
    assert body["version"] == 0
    saved = db.get(WorkoutSubmission, uuid.UUID(body["submissionId"]))
    assert saved.exercise_code == "SQUAT"
    assert saved.counted_reps == 30
    # 미인정 렙도 기록은 남는다
    assert len(db.query(RepEvent).filter_by(submission_id=saved.id).all()) == 32


def test_us01_api026_session_and_daily_cap_are_updated(client):
    session_id, headers = _ready_session(client)

    submission_id = submit(client, headers, session_id).json()["submissionId"]

    session = client.get(f"/workout-sessions/{session_id}", headers=headers).json()
    assert session["status"] == "SUBMITTED"
    assert session["submissionId"] == submission_id
    caps = client.get("/me/daily-caps", headers=headers).json()["items"][0]
    assert caps == {"exerciseCode": "SQUAT", "cap": 200, "reserved": 30, "remaining": 170}


def test_us01_api026_same_idempotency_key_returns_first_result(client, db):
    session_id, headers = _ready_session(client)
    key = str(uuid.uuid4())

    first = submit(client, headers, session_id, key=key)
    again = submit(client, headers, session_id, key=key)

    assert first.status_code == again.status_code == 202
    assert again.json() == first.json()
    assert db.query(WorkoutSubmission).count() == 1


def test_us01_api026_other_key_on_submitted_session_is_409(client):
    session_id, headers = _ready_session(client)
    submit(client, headers, session_id)

    res = submit(client, headers, session_id)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us01_api026_discarded_session_is_409(client):
    session_id, headers = _ready_session(client)
    client.delete(f"/workout-sessions/{session_id}", headers=headers)

    res = submit(client, headers, session_id)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us01_api026_missing_chunk_is_400(client):
    session_id, headers = _ready_session(client, chunks=1)

    res = submit(client, headers, session_id, submit_body(chunks=3))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
    assert res.json()["details"]["missingSeq"] == [2, 3]
    # 실패하면 세션은 그대로라 빠진 청크를 보내고 다시 제출할 수 있다
    assert client.get(f"/workout-sessions/{session_id}", headers=headers).json()["status"] == "ACTIVE"


def test_us01_api026_client_count_above_server_is_422(client, db):
    session_id, headers = _ready_session(client)

    res = submit(client, headers, session_id, submit_body(counted=30, client_count=31))

    assert res.status_code == 422
    assert res.json()["code"] == "SERVER_RECOUNT_MISMATCH"
    assert db.query(WorkoutSubmission).count() == 0


def test_us01_api026_client_may_report_fewer_reps(client):
    """사용자는 인정 횟수를 줄일 수만 있다 (03 R12). 인정량은 서버 값."""
    session_id, headers = _ready_session(client)

    res = submit(client, headers, session_id, submit_body(counted=30, client_count=25))

    assert res.status_code == 202
    assert res.json()["countedReps"] == 30


def _second_submit_after_reserved(client, db, already_reserved):
    """그날 already_reserved회를 이미 예약한 상태에서 30회를 제출한다.

    앞 제출건의 예약량을 DB에서 바꾸고, 끝난 시각을 시작 시각으로 당겨 시간대가 겹치지 않게 한다.
    """
    _, headers = new_player(client)
    first = start_session(client, headers)
    upload_chunks(client, headers, first)
    first_id = uuid.UUID(submit(client, headers, first).json()["submissionId"])
    db.get(DailyCapReservation, first_id).amount = already_reserved
    saved = db.get(WorkoutSubmission, first_id)
    saved.ended_at = saved.started_at
    db.commit()

    second = start_session(client, headers)
    upload_chunks(client, headers, second)
    return submit(client, headers, second, submit_body(counted=30)), headers


def test_us01_api026_daily_cap_full_reserves_zero(client, db):
    """그날 스쿼트 인정량이 이미 200회면 제출건은 생기지만 보상 대상 인정량은 0 (backlog US-01)."""
    res, headers = _second_submit_after_reserved(client, db, 200)

    assert res.status_code == 202
    assert res.json()["countedReps"] == 30
    assert res.json()["reservedReps"] == 0
    assert client.get("/me/daily-caps", headers=headers).json()["items"][0]["reserved"] == 200


def test_us01_api026_partial_cap_reserves_remaining_only(client, db):
    """180회 예약 상태에서 30회 → 남은 20회만 예약 [가정, 노션 DB '부분 예약' 미정]."""
    res, _ = _second_submit_after_reserved(client, db, 180)

    assert res.json()["reservedReps"] == 20


def test_us01_api026_duplicate_time_range_is_409(client):
    _, headers = new_player(client)
    first = start_session(client, headers)
    upload_chunks(client, headers, first)
    assert submit(client, headers, first).status_code == 202
    second = start_session(client, headers)
    upload_chunks(client, headers, second)

    res = submit(client, headers, second)

    assert res.status_code == 409
    assert res.json()["code"] == "DUPLICATE_SUBMISSION"


def test_us01_api026_other_users_session_is_403(client):
    session_id, _ = _ready_session(client)
    _, other = new_player(client)

    assert submit(client, other, session_id).status_code == 403


def test_us01_api026_requires_idempotency_key_and_valid_body(client):
    session_id, headers = _ready_session(client)
    url = f"/workout-sessions/{session_id}/submit"

    assert client.post(url, json=submit_body(), headers=headers).status_code == 400
    for bad in [submit_body() | {"aiConfidence": 1.5}, submit_body() | {"totalChunks": 0}, {}]:
        res = client.post(url, json=bad, headers=headers | {"Idempotency-Key": str(uuid.uuid4())})
        assert res.status_code == 400, bad


def test_us01_api026_without_token_is_401(client):
    assert client.post(f"/workout-sessions/{uuid.uuid4()}/submit", json=submit_body()).status_code == 401
