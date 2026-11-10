"""API-026 세션 종료·운동 제출 — 노션 '전운시 API 명세서' API-026 (US-01 운동하면 렙을 세어 자동 제출).

서버 재계산은 ai/ 엔진 연결 전이라 앱이 보낸 reps 중 counted=true 수를 쓴다 (service.recount_reps, 임시).
"""

import uuid
from datetime import UTC, datetime, timedelta

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
    """두 세션을 같은 시간대에 함께 진행하면(첫 세션이 끝나기 전에 두 번째 시작) 두 번째 제출은 409."""
    _, headers = new_player(client)
    first = start_session(client, headers)
    second = start_session(client, headers)
    upload_chunks(client, headers, first)
    upload_chunks(client, headers, second)
    assert submit(client, headers, first).status_code == 202

    res = submit(client, headers, second)

    assert res.status_code == 409
    assert res.json()["code"] == "DUPLICATE_SUBMISSION"


def test_us01_api026_back_to_back_sessions_are_not_duplicates(client):
    """한 운동을 끝내고 바로 다음 운동을 해도 시간대가 겹치지 않아 둘 다 접수된다."""
    _, headers = new_player(client)
    for _ in range(2):
        session_id = start_session(client, headers)
        upload_chunks(client, headers, session_id)
        assert submit(client, headers, session_id).status_code == 202


def test_us01_api026_future_ended_at_is_clamped_to_server_time(client, db):
    """endedAt이 미래(폰 시계가 빠름·먼 미래 값)면 서버 현재 시각으로 저장한다. 그대로 받으면 이후 정상 제출이
    모두 중복(409)으로 막혔고, 거부하면 시계가 빠른 폰은 아예 제출하지 못했다 (검토에서 찾은 문제)."""
    _, headers = new_player(client)

    for ended in (datetime.now(UTC) + timedelta(minutes=5), datetime(2099, 1, 1, tzinfo=UTC)):
        session_id = start_session(client, headers)
        upload_chunks(client, headers, session_id)
        before = datetime.now(UTC)
        res = submit(client, headers, session_id, submit_body() | {"endedAt": ended.isoformat()})
        # 앞 제출건이 미래로 끝났다면 이 두 번째 제출이 409가 됐을 것
        assert res.status_code == 202, (ended, res.json())
        saved = db.get(WorkoutSubmission, uuid.UUID(res.json()["submissionId"]))
        db.refresh(saved)
        assert before <= saved.ended_at <= datetime.now(UTC)


def test_us01_api026_too_many_reps_is_400(client, db):
    """reps는 최대 500개 (제안값). 넘으면 400이고 아무것도 저장하지 않는다."""
    session_id, headers = _ready_session(client)

    res = submit(client, headers, session_id, submit_body(counted=501))

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"
    assert db.query(RepEvent).count() == 0
    assert submit(client, headers, session_id, submit_body(counted=500)).status_code == 202


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


def test_us01_api026_paused_session_is_409_until_resumed(client):
    """중단된 동안의 불완전 기록은 제출하지 않는다 (노션 API-023). 재개하면 제출된다."""
    _, headers = new_player(client)
    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id)
    pause = {"reason": "APP_BACKGROUND", "at": datetime.now(UTC).isoformat()}
    assert client.post(f"/workout-sessions/{session_id}/pause", json=pause, headers=headers).status_code == 200

    res = submit(client, headers, session_id)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"
    assert client.get(f"/workout-sessions/{session_id}", headers=headers).json()["status"] == "PAUSED"
    assert client.post(f"/workout-sessions/{session_id}/resume", headers=headers).status_code == 200
    assert submit(client, headers, session_id).status_code == 202
