"""확인 요청·승인·반려 테스트 공통 도구. 실제 API로 세션 → (무작위 동작 확인) → 제출 → 스냅샷(PREPARED)까지 만든다."""

from tests.character_helpers import new_player
from tests.submission_helpers import internal_headers, prepare, submit, submit_body, upload_chunks


def new_prepared(client, *, confidence: float = 0.94, liveness: bool = True, counted: int = 30, headers=None):
    """PREPARED 제출건 1건을 만든다. (submission_id, 신청자 헤더)를 돌려준다.

    liveness=True면 무작위 동작 확인을 통과시키고, False면 보내지 않는다(NULL).
    """
    if headers is None:
        _, headers = new_player(client)
    res = client.post("/workout-sessions", json={"exerciseCode": "SQUAT"}, headers=headers)
    assert res.status_code == 201, res.json()
    started = res.json()
    session_id = started["sessionId"]
    if liveness:
        live = client.post(
            f"/workout-sessions/{session_id}/liveness",
            json={
                "challengeId": started["liveness"]["challengeId"],
                "detectedAction": started["liveness"]["action"],
                "score": 0.95,
                "detectedAt": "2026-11-10T05:01:12Z",
            },
            headers=headers,
        )
        assert live.status_code == 200, live.json()
    upload_chunks(client, headers, session_id)
    res = submit(client, headers, session_id, {**submit_body(counted=counted), "aiConfidence": confidence})
    assert res.status_code == 202, res.json()
    submission_id = res.json()["submissionId"]
    assert prepare(client, submission_id).status_code == 200
    return submission_id, headers


def auto_approval(client, submission_id: str):
    """자동 승인 판정 (API-033)."""
    return client.post(f"/internal/submissions/{submission_id}/auto-approval", headers=internal_headers())


def version_of(client, submission_id: str, headers) -> int:
    res = client.get(f"/submissions/{submission_id}", headers=headers)
    assert res.status_code == 200, res.json()
    return res.json()["version"]
