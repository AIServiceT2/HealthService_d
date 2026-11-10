"""API-039 확인자 반려 — backlog US-08 확인자가 사유와 함께 반려."""

from sqlalchemy import text

from tests.character_helpers import new_player
from tests.review_helpers import approve, pending_review, reject, version_of


def daily_reserved(client, headers):
    return client.get("/me/daily-caps", headers=headers).json()["items"][0]["reserved"]


def test_us08_api039_reject_closes_and_releases_cap(client, db):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)
    assert daily_reserved(client, requester) == 30

    res = reject(client, sid, leader_headers, version)

    assert res.status_code == 200
    assert res.json() == {
        "submissionId": sid,
        "submissionStatus": "CLOSED",
        "releasedReps": 30,
        "cameraSessionClosed": True,
        "version": version + 2,
    }
    detail = client.get(f"/submissions/{sid}", headers=requester).json()
    assert detail["status"] == "CLOSED"
    assert detail["reservedReps"] == 0
    assert daily_reserved(client, requester) == 0
    reason = db.execute(
        text("SELECT reason_code, reason_text FROM review_request WHERE submission_id = :id"), {"id": sid}
    ).one()
    assert tuple(reason) == ("RECORD_ANOMALY", "12~15회가 너무 빠름")


def test_us08_api039_requires_reason_code_and_text(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)

    for body in (
        {"reasonText": "설명만"},
        {"reasonCode": "RECORD_ANOMALY"},
        {"reasonCode": "RECORD_ANOMALY", "reasonText": "   "},
        {},
    ):
        res = reject(client, sid, leader_headers, version, body)
        assert res.status_code == 400, body
        assert res.json()["message"] == "반려 사유 코드와 설명이 필요합니다."

    assert client.get(f"/submissions/{sid}", headers=requester).json()["status"] == "PENDING_REVIEW"


def test_us08_api039_rejects_unknown_reason_code(client):
    sid, requester, _, leader_headers = pending_review(client)

    res = reject(client, sid, leader_headers, version_of(client, sid, requester), {"reasonCode": "LAZY", "reasonText": "x"})

    assert res.status_code == 400
    assert res.json()["details"] == {"reason": "UNKNOWN_REASON_CODE"}


def test_us08_api039_only_assigned_reviewer(client):
    sid, requester, _, _ = pending_review(client)
    _, stranger = new_player(client)
    version = version_of(client, sid, requester)

    assert reject(client, sid, stranger, version).status_code == 403
    assert reject(client, sid, requester, version).status_code == 403  # 신청자 본인 반려 불가


def test_us08_api039_closed_cannot_change_again(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)
    reject(client, sid, leader_headers, version)

    assert reject(client, sid, leader_headers, version + 2).status_code == 409
    assert approve(client, sid, leader_headers, version + 2).status_code == 409
    cancel = client.post(f"/submissions/{sid}/cancel", headers=requester | {"If-Match": f'"{version + 2}"'})
    assert cancel.status_code == 409


def test_us08_api039_stale_version_is_412(client):
    sid, requester, _, leader_headers = pending_review(client)

    res = reject(client, sid, leader_headers, version_of(client, sid, requester) - 1)

    assert res.status_code == 412
