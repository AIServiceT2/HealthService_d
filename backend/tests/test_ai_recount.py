"""API-026과 AI 내부 HTTP 계약 사이의 변환 및 실패 처리."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import TypeAdapter

from app.modules.submission import service
from app.modules.submission.ai_recount import _engine_chunks, recount_workout
from app.modules.submission.models import DailyCapReservation, RepEvent, WorkoutSubmission
from app.modules.workout_session.catalog import CHUNK_MAX_BYTES, CHUNK_MAX_FRAMES
from app.modules.workout_session.models import PoseChunk
from tests.character_helpers import new_player
from tests.submission_helpers import start_session, submit, submit_body


@pytest.fixture
def session_id_and_headers(client, monkeypatch):
    monkeypatch.setattr(service, "recount_workout", recount_workout)
    monkeypatch.setenv("AI_INTERNAL_TOKEN", "test-only-ai-token")
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai:8001/")
    _, headers = new_player(client)
    session_id = start_session(client, headers)
    now = int(datetime.now(UTC).timestamp() * 1000)
    for seq in (2, 1):
        response = client.put(
            f"/workout-sessions/{session_id}/pose-chunks/{seq}",
            json={
                "seq": seq,
                "frames": [{"t": now + seq * 100, "kp": [None] * 5 + [[0.5, 0.5, 0.9]] * 12}],
            },
            headers=headers,
        )
        assert response.status_code == 200
    return session_id, headers


def _ai_result(payload):
    frames = [frame for chunk in payload["chunks"] for frame in chunk["frames"]]
    return {
        "result": {
            "recognizedReps": 1,
            "aiConfidence": 0.73,
            "reps": [
                {"index": 1, "endT": frames[0]["t"], "accepted": True},
                {"index": 2, "endT": frames[1]["t"], "accepted": False},
            ],
            "liveness": {"status": "PASSED"},
        }
    }


def test_submit_uses_ai_reps_and_replays_without_another_call(
    client, db, monkeypatch, session_id_and_headers
):
    session_id, headers = session_id_and_headers
    calls = []

    def post(url, *, json, headers, **_options):
        assert url == "http://ai:8001/internal/recount"
        assert headers["X-Internal-Token"] == "test-only-ai-token"
        assert json["meta"]["sessionId"] == session_id
        assert json["meta"]["device"]["modelVersion"] == "movenet-lightning@4"
        assert [chunk["seq"] for chunk in json["chunks"]] == [0, 1]
        frame = json["chunks"][0]["frames"][0]
        assert frame["landmarks"][:5] == [None] * 5
        assert frame["landmarks"][5] == {"x": 0.5, "y": 0.5, "z": None, "visibility": 0.9}
        calls.append(json)
        return httpx.Response(200, json=_ai_result(json), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    key = str(uuid.uuid4())
    body = submit_body(counted=4, client_count=1, chunks=2)
    response = submit(client, headers, session_id, body, key)
    assert response.status_code == 202, response.json()
    assert response.json()["countedReps"] == response.json()["reservedReps"] == 1
    submission_id = uuid.UUID(response.json()["submissionId"])
    assert db.get(WorkoutSubmission, submission_id).confidence == 0.73
    rows = db.query(RepEvent).filter_by(submission_id=submission_id).order_by(RepEvent.rep_no).all()
    assert [row.counted for row in rows] == [True, False]
    assert (rows[1].ts - rows[0].ts).total_seconds() == 0.1
    assert client.get(f"/workout-sessions/{session_id}", headers=headers).json()["livenessPassed"]

    del body["poseCapture"]
    assert submit(client, headers, session_id, body, key).json() == response.json()
    assert len(calls) == 1


def test_ai_failure_and_mismatch_leave_session_retryable(
    client, db, monkeypatch, session_id_and_headers
):
    session_id, headers = session_id_and_headers
    key = str(uuid.uuid4())
    body = submit_body(counted=2, chunks=2)

    def timeout(url, **_options):
        raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", timeout)
    response = submit(client, headers, session_id, body, key)
    assert response.status_code == 503
    assert response.json()["code"] == "AI_UNAVAILABLE"

    def post(url, *, json, **_options):
        return httpx.Response(200, json=_ai_result(json), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    response = submit(client, headers, session_id, body, key)
    assert response.status_code == 422
    assert response.json()["details"] == {"clientRepCount": 2, "serverRepCount": 1}
    assert db.query(WorkoutSubmission).count() == db.query(DailyCapReservation).count() == 0
    assert client.get(f"/workout-sessions/{session_id}", headers=headers).json()["status"] == "ACTIVE"

    body["clientRepCount"] = 1
    assert submit(client, headers, session_id, body, key).status_code == 202


def test_expanded_chunk_stays_under_the_ai_byte_limit():
    session_id = uuid.uuid4()
    keypoints = [None] * 11 + [[0.123456789, 0.123456789, 0.987654321]] * 22
    frames = [{"t": 650 * seq, "kp": keypoints} for seq in range(CHUNK_MAX_FRAMES - 30)]
    stored = PoseChunk(session_id=session_id, seq=1, frames=frames)
    encoder = TypeAdapter(dict)
    assert len(encoder.dump_json({"seq": 1, "frames": frames})) < CHUNK_MAX_BYTES

    chunks = _engine_chunks(str(session_id), [stored], 0)

    assert len(chunks) > 1
    assert [chunk["seq"] for chunk in chunks] == list(range(len(chunks)))
    assert all(len(encoder.dump_json(chunk)) <= CHUNK_MAX_BYTES for chunk in chunks)
    assert [frame["t"] for chunk in chunks for frame in chunk["frames"]] == [
        frame["t"] for frame in frames
    ]
