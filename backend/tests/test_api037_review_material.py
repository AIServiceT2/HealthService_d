"""API-037 확인 자료 열람 — backlog US-07 (권한): 확인자 화면에 얼굴·나이·길드명이 없고, 요청받지 않은 사용자는 볼 수 없다."""

from tests.character_helpers import new_player
from tests.review_helpers import pending_review
from tests.submission_helpers import new_submission


def material(client, sid, headers):
    return client.get(f"/review-requests/{sid}", headers=headers)


def test_us07_api037_reviewer_sees_material_with_etag(client):
    sid, requester, _, leader_headers = pending_review(client, confidence=0.82)
    version = client.get(f"/submissions/{sid}", headers=requester).json()["version"]

    res = material(client, sid, leader_headers)

    assert res.status_code == 200
    assert res.headers["ETag"] == f'"{version}"'
    assert res.json() == {
        "submissionId": sid,
        "status": "PENDING_REVIEW",
        "version": version,
        "requester": {"nickname": "플레이어"},
        "exerciseCode": "SQUAT",
        "countedReps": 30,
        "confidence": 0.82,
        "skeletonReplayUrl": None,
        "summary": None,
        "anomalies": [],
        "painNotice": None,
    }


def test_us07_api037_hides_face_age_and_guild(client):
    sid, _, _, leader_headers = pending_review(client)
    body = material(client, sid, leader_headers).json()

    keys = set(body) | set(body["requester"])
    assert not any(word in key.lower() for key in keys for word in ("face", "birth", "age", "guild", "userid"))


def test_us07_api037_only_assigned_reviewer(client):
    sid, requester, _, _ = pending_review(client)
    _, stranger = new_player(client)

    assert material(client, sid, stranger).status_code == 403
    assert material(client, sid, requester).status_code == 403  # 신청자 본인도 확인자 화면은 못 봄


def test_us07_api037_no_review_request_is_404(client):
    sid, headers = new_submission(client)

    res = material(client, sid, headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"
