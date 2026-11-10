"""API-038 확인자 승인 — backlog US-07 (정상)·US-06 (취소와 승인이 동시에 오면 하나만)."""

import threading

from fastapi.testclient import TestClient

from app.main import app
from tests.character_helpers import new_player
from tests.review_helpers import approve, pending_review, version_of


def test_us07_api038_reviewer_approves(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)

    res = approve(client, sid, leader_headers, version)

    assert res.status_code == 200
    assert res.json() == {
        "submissionId": sid,
        "submissionStatus": "APPROVED",
        "approvalPath": "REVIEWER",
        "version": version + 1,
    }
    detail = client.get(f"/submissions/{sid}", headers=requester).json()
    assert detail["status"] == "APPROVED"
    assert detail["approvalPath"] == "REVIEWER"


def test_us07_api038_only_assigned_reviewer(client):
    sid, requester, _, _ = pending_review(client)
    _, stranger = new_player(client)
    version = version_of(client, sid, requester)

    assert approve(client, sid, stranger, version).status_code == 403
    assert approve(client, sid, requester, version).status_code == 403  # 신청자 본인 승인 불가
    assert version_of(client, sid, requester) == version


def test_us07_api038_stale_version_is_412(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)

    res = approve(client, sid, leader_headers, version - 1)

    assert res.status_code == 412
    assert res.json()["code"] == "CONCURRENT_UPDATE"


def test_us07_api038_canceled_cannot_be_approved(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)
    assert client.post(f"/submissions/{sid}/cancel", headers=requester | {"If-Match": f'"{version}"'}).status_code == 200

    res = approve(client, sid, leader_headers, version + 1)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us07_api038_approve_twice_is_409(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)
    approve(client, sid, leader_headers, version)

    assert approve(client, sid, leader_headers, version + 1).status_code == 409


def test_us06_api038_cancel_and_approve_at_the_same_time_only_one_wins(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = version_of(client, sid, requester)
    barrier = threading.Barrier(2)
    results = {}

    def run(name, method):
        with TestClient(app) as c:
            barrier.wait()
            results[name] = method(c).status_code

    cancel = threading.Thread(
        target=run,
        args=("cancel", lambda c: c.post(f"/submissions/{sid}/cancel", headers=requester | {"If-Match": f'"{version}"'})),
    )
    approval = threading.Thread(target=run, args=("approve", lambda c: approve(c, sid, leader_headers, version)))
    cancel.start(), approval.start()
    cancel.join(), approval.join()

    assert sorted(results.values()) == [200, 412]
    status = client.get(f"/submissions/{sid}", headers=requester).json()["status"]
    assert status == ("CANCELED" if results["cancel"] == 200 else "APPROVED")


def test_us07_api038_missing_review_is_404(client):
    _, headers = new_player(client)
    assert approve(client, "00000000-0000-0000-0000-000000000000", headers, 0).status_code == 404
