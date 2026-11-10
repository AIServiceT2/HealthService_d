"""운동 세션 API 테스트 — 노션 '전운시 API 명세서' API-018~025 (US-01 운동하면 렙을 세어 자동 제출의 앞단).

로그인은 실제 회원 가입·로그인으로 받은 access token을 쓴다 (tests/character_helpers.py).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from tests.character_helpers import new_player

# ---- API-018 운동 목록·판정 기준·튜토리얼 ----


def test_us01_api018_lists_squat_only(client):
    _, headers = new_player(client)

    res = client.get("/exercises", headers=headers)

    assert res.status_code == 200
    assert res.json() == {
        "catalogVersion": "cat_2026-11-01",
        "items": [
            {
                "code": "SQUAT",
                "name": "스쿼트",
                "dailyCap": 200,
                "criteria": {"kneeAngleMax": None},
                "recommendedCameraAngle": None,
                "tutorialUrl": None,
            }
        ],
    }


def test_us01_api018_requires_login(client):
    res = client.get("/exercises")
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


# ---- API-019 내 일일 상한 조회 ----


def test_us01_api019_returns_today_kst_caps(client):
    _, headers = new_player(client)

    res = client.get("/me/daily-caps", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["date"] == datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    # 제출(API-026)이 없어 예약 0 → 상한 200이 그대로 남음
    assert body["items"] == [{"exerciseCode": "SQUAT", "cap": 200, "reserved": 0, "remaining": 200}]


def test_us01_api019_requires_login(client):
    assert client.get("/me/daily-caps").status_code == 401


# ---- API-020 운동 세션 시작 ----

START_BODY = {
    "exerciseCode": "SQUAT",
    "goal": {"reps": 30, "sets": 1},
    "target": {"type": "DUNGEON", "id": "6f1c2b1e-8a1d-4b8e-9a51-0d6c1f7f2a10"},
    "device": {"os": "android", "model": "SM-S921N"},
}


def start_session(client, headers, body=START_BODY):
    res = client.post("/workout-sessions", json=body, headers=headers)
    assert res.status_code == 201, res.json()
    return res.json()


def test_us01_api020_starts_active_session_with_liveness_challenge(client):
    _, headers = new_player(client)

    body = start_session(client, headers)

    assert body["status"] == "ACTIVE"
    assert body["catalogVersion"] == "cat_2026-11-01"
    assert body["remainingDailyCap"] == 200
    assert body["liveness"]["action"] in {"RAISE_LEFT_HAND", "RAISE_RIGHT_HAND", "RAISE_BOTH_HANDS"}
    assert body["liveness"]["timeoutSec"] == 10
    assert body["chunkSpec"] == {"maxFrames": 300, "maxBytes": 262144}
    assert {"sessionId", "liveness"} <= body.keys()
    assert "challengeId" in body["liveness"]


def test_us01_api020_goal_target_device_are_optional(client):
    _, headers = new_player(client)
    start_session(client, headers, {"exerciseCode": "SQUAT"})


def test_us01_api020_rejects_unknown_exercise(client):
    _, headers = new_player(client)

    res = client.post("/workout-sessions", json={**START_BODY, "exerciseCode": "PUSHUP"}, headers=headers)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_us01_api020_rejects_bad_goal_and_target(client):
    _, headers = new_player(client)
    bad_goal = {**START_BODY, "goal": {"reps": 0, "sets": 1}}
    bad_target = {**START_BODY, "target": {"type": "RAID", "id": START_BODY["target"]["id"]}}

    assert client.post("/workout-sessions", json=bad_goal, headers=headers).status_code == 400
    assert client.post("/workout-sessions", json=bad_target, headers=headers).status_code == 400


def test_us01_api020_requires_login(client):
    assert client.post("/workout-sessions", json=START_BODY).status_code == 401


# ---- API-021 무작위 동작 확인 결과 전송 ----


def liveness_body(started, action=None):
    return {
        "challengeId": started["liveness"]["challengeId"],
        "detectedAction": action or started["liveness"]["action"],
        "score": 0.93,
        "detectedAt": "2026-11-09T05:01:12Z",
    }


def post_liveness(client, headers, started, body=None):
    return client.post(
        f"/workout-sessions/{started['sessionId']}/liveness",
        json=body or liveness_body(started),
        headers=headers,
    )


def test_us01_api021_passes_when_action_matches(client):
    _, headers = new_player(client)
    started = start_session(client, headers)

    res = post_liveness(client, headers, started)

    assert res.status_code == 200
    assert res.json() == {"passed": True, "retryAllowed": False}


def test_us01_api021_fails_on_wrong_action_and_cannot_retry(client):
    _, headers = new_player(client)
    started = start_session(client, headers)
    wrong = next(a for a in ("RAISE_LEFT_HAND", "RAISE_RIGHT_HAND") if a != started["liveness"]["action"])

    res = post_liveness(client, headers, started, liveness_body(started, wrong))

    assert res.status_code == 422
    assert res.json()["code"] == "LIVENESS_FAILED"
    # 한 번 판정하면 다시 보낼 수 없음
    assert post_liveness(client, headers, started).status_code == 409


def test_us01_api021_fails_after_timeout(client, db):
    _, headers = new_player(client)
    started = start_session(client, headers)
    db.execute(
        text("UPDATE workout_session SET liveness_issued_at = now() - interval '11 seconds' WHERE id = :id"),
        {"id": started["sessionId"]},
    )
    db.commit()

    res = post_liveness(client, headers, started)

    assert res.status_code == 422
    assert res.json()["code"] == "LIVENESS_FAILED"


def test_us01_api021_rejects_other_challenge_id(client):
    _, headers = new_player(client)
    started = start_session(client, headers)
    body = {**liveness_body(started), "challengeId": "00000000-0000-0000-0000-000000000000"}

    res = post_liveness(client, headers, started, body)

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_us01_api021_only_owner(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    started = start_session(client, owner)

    assert post_liveness(client, other, started).status_code == 403


# ---- API-022 관절 좌표 청크 업로드 ----


def mediapipe_frame(t=1731128472123):
    # 33개 중 얼굴(0~10번)은 null
    return {"t": t, "kp": [None] * 11 + [[0.5, 0.5, 0.9]] * 22}


def put_chunk(client, headers, session_id, seq, frames=None, body_seq=None):
    return client.put(
        f"/workout-sessions/{session_id}/pose-chunks/{seq}",
        json={"seq": body_seq or seq, "frames": frames or [mediapipe_frame()]},
        headers=headers,
    )


def test_us01_api022_stores_chunks_and_returns_received_seqs(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    assert put_chunk(client, headers, sid, 2).json() == {"received": [2]}
    res = put_chunk(client, headers, sid, 1)

    assert res.status_code == 200
    assert res.json() == {"received": [1, 2]}


def test_us01_api022_same_seq_overwrites(client, db):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    put_chunk(client, headers, sid, 1, [mediapipe_frame(t=1)])

    res = put_chunk(client, headers, sid, 1, [mediapipe_frame(t=2), mediapipe_frame(t=3)])

    assert res.json() == {"received": [1]}
    frames = db.execute(
        text("SELECT frames FROM pose_chunk WHERE session_id = :id AND seq = 1"), {"id": sid}
    ).scalar_one()
    assert [f["t"] for f in frames] == [2, 3]


def test_us01_api022_accepts_movenet_17_keypoints(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    frame = {"t": 1, "kp": [None] * 5 + [[0.5, 0.5, 0.9]] * 12}

    assert put_chunk(client, headers, sid, 1, [frame]).status_code == 200


def test_us01_api022_rejects_face_landmarks(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    frame = mediapipe_frame()
    frame["kp"][0] = [0.5, 0.2, 0.99]  # 코 좌표를 보냄

    res = put_chunk(client, headers, sid, 1, [frame])

    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "FACE_LANDMARK_INCLUDED"}


def test_us01_api022_rejects_unknown_keypoint_count(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    res = put_chunk(client, headers, sid, 1, [{"t": 1, "kp": [[0.5, 0.5, 0.9]] * 13}])

    assert res.json()["details"] == {"reason": "UNKNOWN_KEYPOINT_LAYOUT"}


def test_us01_api022_rejects_too_many_frames_and_too_large(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    # 프레임 수를 먼저 검사한다 (짧은 좌표 301프레임은 약 130KB로 크기 제한 안쪽)
    many = [mediapipe_frame(t=i) for i in range(301)]
    res = put_chunk(client, headers, sid, 1, many)
    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "TOO_MANY_FRAMES"}

    # 300프레임이라도 본문이 256KB를 넘으면 거부 (긴 소수 좌표로 약 360KB)

    long_floats = {"t": 1, "kp": [None] * 11 + [[0.123456789012345, 0.123456789012345, 0.99]] * 22}
    big = [long_floats] * 300
    res = put_chunk(client, headers, sid, 2, big)
    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "CHUNK_TOO_LARGE"}


def test_us01_api022_rejects_seq_mismatch(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    res = put_chunk(client, headers, sid, 1, body_seq=2)

    assert res.json()["details"] == {"reason": "SEQ_MISMATCH"}


def test_us01_api022_only_owner(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    sid = start_session(client, owner)["sessionId"]

    assert put_chunk(client, other, sid, 1).status_code == 403


# ---- API-023 세션 일시중지 ----

PAUSE_BODY = {"reason": "APP_BACKGROUND", "at": "2026-11-09T05:03:00Z"}


def pause(client, headers, sid, body=PAUSE_BODY):
    return client.post(f"/workout-sessions/{sid}/pause", json=body, headers=headers)


def test_us01_api023_pauses_active_session(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    res = pause(client, headers, sid)

    assert res.status_code == 200
    assert res.json() == {"sessionId": sid, "status": "PAUSED"}


def test_us01_api023_rejects_when_not_active(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    pause(client, headers, sid)

    res = pause(client, headers, sid)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us01_api023_rejects_unknown_reason(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    assert pause(client, headers, sid, {**PAUSE_BODY, "reason": "TIRED"}).status_code == 400


def test_us01_api023_only_owner(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    sid = start_session(client, owner)["sessionId"]

    assert pause(client, other, sid).status_code == 403


# ---- API-024 세션 재개 ----


def resume(client, headers, sid):
    return client.post(f"/workout-sessions/{sid}/resume", headers=headers)


def test_us01_api024_resumes_paused_session_with_received_chunks(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    put_chunk(client, headers, sid, 1)
    put_chunk(client, headers, sid, 3)
    pause(client, headers, sid)

    res = resume(client, headers, sid)

    assert res.status_code == 200
    assert res.json() == {"sessionId": sid, "status": "ACTIVE", "receivedChunks": [1, 3]}


def test_us01_api024_rejects_when_not_paused(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    res = resume(client, headers, sid)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us01_api024_only_owner(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    sid = start_session(client, owner)["sessionId"]
    pause(client, owner, sid)

    assert resume(client, other, sid).status_code == 403


# ---- API-025 세션 상태 조회 ----


def test_us01_api025_returns_session_state(client):
    _, headers = new_player(client)
    started = start_session(client, headers)
    sid = started["sessionId"]
    post_liveness(client, headers, started)
    put_chunk(client, headers, sid, 1)

    res = client.get(f"/workout-sessions/{sid}", headers=headers)

    assert res.status_code == 200
    assert res.json() == {
        "sessionId": sid,
        "status": "ACTIVE",
        "exerciseCode": "SQUAT",
        "livenessPassed": True,
        "receivedChunks": [1],
        "submissionId": None,
    }


def test_us01_api025_liveness_is_null_before_check(client):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]

    assert client.get(f"/workout-sessions/{sid}", headers=headers).json()["livenessPassed"] is None


def test_us01_api025_forbidden_for_other_user_and_404_for_missing(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    sid = start_session(client, owner)["sessionId"]

    forbidden = client.get(f"/workout-sessions/{sid}", headers=other)
    missing = client.get("/workout-sessions/00000000-0000-0000-0000-000000000000", headers=owner)

    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "FORBIDDEN"
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"


# ---- API-027 세션 폐기 ----


def discard(client, headers, sid):
    return client.delete(f"/workout-sessions/{sid}", headers=headers)


def test_us01_api027_discards_session_and_deletes_chunks(client, db):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    put_chunk(client, headers, sid, 1)
    put_chunk(client, headers, sid, 2)

    res = discard(client, headers, sid)

    assert res.status_code == 204
    detail = client.get(f"/workout-sessions/{sid}", headers=headers).json()
    assert detail["status"] == "DISCARDED"
    assert detail["receivedChunks"] == []
    count = db.execute(
        text("SELECT count(*) FROM pose_chunk WHERE session_id = :id"), {"id": sid}
    ).scalar_one()
    assert count == 0


def test_us01_api027_discarded_session_rejects_further_changes(client):
    _, headers = new_player(client)
    started = start_session(client, headers)
    sid = started["sessionId"]
    discard(client, headers, sid)

    assert discard(client, headers, sid).status_code == 204  # 다시 보내도 같은 결과
    assert put_chunk(client, headers, sid, 1).status_code == 409
    assert pause(client, headers, sid).status_code == 409
    assert post_liveness(client, headers, started).status_code == 409


def test_us01_api027_rejects_submitted_session(client, db):
    _, headers = new_player(client)
    sid = start_session(client, headers)["sessionId"]
    # 제출(API-026)이 아직 없어 DB에서 상태만 바꿔 둔다
    db.execute(text("UPDATE workout_session SET status = 'SUBMITTED' WHERE id = :id"), {"id": sid})
    db.commit()

    res = discard(client, headers, sid)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us01_api027_only_owner(client):
    _, owner = new_player(client)
    _, other = new_player(client)
    sid = start_session(client, owner)["sessionId"]

    assert discard(client, other, sid).status_code == 403


def test_us01_api021_paused_session_gets_specific_message(client):
    _, headers = new_player(client)
    started = start_session(client, headers)
    pause(client, headers, started["sessionId"])

    res = post_liveness(client, headers, started)

    assert res.status_code == 409
    assert res.json()["message"] == "일시중지된 세션입니다. 재개한 뒤 보내 주세요."
    resume(client, headers, started["sessionId"])
    assert post_liveness(client, headers, started).status_code == 200
