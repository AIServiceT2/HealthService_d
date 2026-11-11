"""확인 요청·승인·반려 테스트 공통 도구. 실제 API로 세션 → (무작위 동작 확인) → 제출 → 스냅샷(PREPARED)까지 만든다."""

import uuid

from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild
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


def leader_and_member(client) -> tuple[uuid.UUID, dict[str, str], dict[str, str]]:
    """길드장 1명과 같은 길드 소속원 1명. (길드장 user_id, 길드장 헤더, 소속원 헤더).

    확인자는 같은 길드원(API-017 지인 목록)만 고를 수 있다 (review/service.py allowed_reviewers).
    """
    guild_id, leader_id, leader_headers = new_guild(client)
    _, member_headers = join_with_code(client, guild_id, leader_headers)
    return leader_id, leader_headers, member_headers


def request_review(client, submission_id: str, headers, reviewer_id, *, version=None, confirmed=True):
    """확인 요청 (API-035). version을 주지 않으면 현재 version을 읽어 If-Match에 넣는다."""
    if version is None:
        version = version_of(client, submission_id, headers)
    return client.post(
        f"/submissions/{submission_id}/review-requests",
        json={"reviewerUserId": str(reviewer_id), "sharePreviewConfirmed": confirmed},
        headers=headers | {"If-Match": f'"{version}"'},
    )


def pending_review(client, *, confidence: float = 0.82):
    """PENDING_REVIEW 건 1건. (submission_id, 신청자 헤더, 길드장(확인자) user_id, 길드장 헤더)."""
    leader_id, leader_headers, member_headers = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=confidence, headers=member_headers)
    res = request_review(client, sid, member_headers, leader_id)
    assert res.status_code == 201, res.json()
    return sid, member_headers, leader_id, leader_headers


def approve(client, submission_id: str, reviewer_headers, version: int):
    """확인자 승인 (API-038)."""
    return client.post(
        f"/review-requests/{submission_id}/approve", headers=reviewer_headers | {"If-Match": f'"{version}"'}
    )


def reject(client, submission_id: str, reviewer_headers, version: int, body=None):
    """확인자 반려 (API-039)."""
    return client.post(
        f"/review-requests/{submission_id}/reject",
        json=body if body is not None else {"reasonCode": "RECORD_ANOMALY", "reasonText": "12~15회가 너무 빠름"},
        headers=reviewer_headers | {"If-Match": f'"{version}"'},
    )
