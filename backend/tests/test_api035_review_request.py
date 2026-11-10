"""API-035 지인·길드장에게 확인 요청 — backlog US-07 애매한 건을 지인·길드장에게 확인 요청."""

from tests.character_helpers import new_player
from tests.review_helpers import (
    auto_approval,
    leader_and_member,
    new_prepared,
    request_review,
    version_of,
)


def test_us07_api035_sends_to_guild_leader_and_becomes_pending_review(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)
    before = version_of(client, sid, member)

    res = request_review(client, sid, member, leader_id)

    assert res.status_code == 201
    body = res.json()
    assert body["submissionId"] == sid
    assert body["submissionStatus"] == "PENDING_REVIEW"
    assert body["version"] == before + 1
    assert body["reviewer"] == {"userId": str(leader_id), "nickname": "플레이어"}
    assert body["requestedAt"]
    assert client.get(f"/submissions/{sid}", headers=member).json()["status"] == "PENDING_REVIEW"


def test_us07_api035_rejects_self_as_reviewer(client):
    # 길드장이 자기 제출건을 자기에게 보내는 경우
    leader_id, leader_headers, _ = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=leader_headers)

    res = request_review(client, sid, leader_headers, leader_id)

    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "SELF_REVIEWER"}


def test_us07_api035_requires_share_preview_confirmed(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)

    res = request_review(client, sid, member, leader_id, confirmed=False)

    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "SHARE_PREVIEW_NOT_CONFIRMED"}
    assert client.get(f"/submissions/{sid}", headers=member).json()["status"] == "PREPARED"


def test_us07_api035_rejects_reviewer_who_is_not_my_guild_leader(client):
    _, _, member = leader_and_member(client)
    stranger_id, _ = new_player(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)

    res = request_review(client, sid, member, stranger_id)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_us07_api035_only_one_request_per_submission(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)
    request_review(client, sid, member, leader_id)

    res = request_review(client, sid, member, leader_id)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us07_api035_rejects_already_approved(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.94, liveness=True, headers=member)
    auto_approval(client, sid)

    assert request_review(client, sid, member, leader_id).status_code == 409


def test_us07_api035_rejects_auto_approvable(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.94, liveness=True, headers=member)

    assert request_review(client, sid, member, leader_id).status_code == 409


def test_us07_api035_stale_version_is_412(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)
    current = version_of(client, sid, member)

    res = request_review(client, sid, member, leader_id, version=current + 1)

    assert res.status_code == 412
    assert res.json()["code"] == "CONCURRENT_UPDATE"


def test_us07_api035_requires_if_match(client):
    leader_id, _, member = leader_and_member(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)

    res = client.post(
        f"/submissions/{sid}/review-requests",
        json={"reviewerUserId": str(leader_id), "sharePreviewConfirmed": True},
        headers=member,
    )

    assert res.status_code == 400


def test_us07_api035_only_owner(client):
    leader_id, _, member = leader_and_member(client)
    _, stranger = new_player(client)
    sid, _ = new_prepared(client, confidence=0.82, headers=member)
    version = version_of(client, sid, member)

    res = request_review(client, sid, stranger, leader_id, version=version)

    assert res.status_code == 403
    assert client.get(f"/submissions/{sid}", headers=member).json()["status"] == "PREPARED"
