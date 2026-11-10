"""제출건 API 테스트 공통 도구. 세션 시작(API-020) → 청크 업로드(API-022) → 제출(API-026)을 실제 API로 한다."""

import uuid
from datetime import UTC, datetime, timedelta

from tests.character_helpers import new_player

# MoveNet(17개) 형식. 얼굴 0~4번은 null이어야 한다 (API-022)
_KP = [None] * 5 + [[0.5, 0.5, 0.9]] * 12


def start_session(client, headers) -> str:
    res = client.post("/workout-sessions", json={"exerciseCode": "SQUAT"}, headers=headers)
    assert res.status_code == 201, res.json()
    return res.json()["sessionId"]


def upload_chunks(client, headers, session_id: str, count: int = 1) -> None:
    for seq in range(1, count + 1):
        res = client.put(
            f"/workout-sessions/{session_id}/pose-chunks/{seq}",
            json={"seq": seq, "frames": [{"t": 1_000 * seq, "kp": _KP}]},
            headers=headers,
        )
        assert res.status_code == 200, res.json()


def submit_body(counted: int = 30, uncounted: int = 0, client_count: int | None = None, chunks: int = 1) -> dict:
    # 끝난 시각은 제출하는 지금 (서버 현재 시각보다 미래면 400, API-026)
    now = datetime.now(UTC)
    total = counted + uncounted
    reps = [
        {"repNo": i + 1, "ts": (now - timedelta(seconds=total - i)).isoformat(), "counted": i < counted}
        for i in range(total)
    ]
    return {
        "totalChunks": chunks,
        "endedAt": now.isoformat(),
        "clientRepCount": counted if client_count is None else client_count,
        "reps": reps,
        "aiConfidence": 0.94,
    }


def submit(client, headers, session_id: str, body: dict | None = None, key: str | None = None):
    return client.post(
        f"/workout-sessions/{session_id}/submit",
        json=body or submit_body(),
        headers=headers | {"Idempotency-Key": key or str(uuid.uuid4())},
    )


def new_submission(client, counted: int = 30, headers=None) -> tuple[str, dict[str, str]]:
    """새 사용자(또는 headers의 사용자)가 스쿼트를 counted회 해서 제출한다. (submission_id, 헤더)."""
    if headers is None:
        _, headers = new_player(client)
    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id)
    res = submit(client, headers, session_id, submit_body(counted=counted))
    assert res.status_code == 202, res.json()
    return res.json()["submissionId"], headers


# 서버 내부 호출(/internal) 테스트 전용 토큰 (실제 값이 아님)
TEST_INTERNAL_TOKEN = "test-only-internal-token"


def internal_headers() -> dict[str, str]:
    return {"X-Internal-Token": TEST_INTERNAL_TOKEN, "Idempotency-Key": str(uuid.uuid4())}


def prepare(client, submission_id: str):
    """보상 스냅샷 계산·고정 (API-031)."""
    return client.post(f"/internal/submissions/{submission_id}/snapshot", headers=internal_headers())
