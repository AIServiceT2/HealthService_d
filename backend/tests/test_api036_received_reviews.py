"""API-036 받은 확인 요청 목록 — backlog US-07 (권한): 요청받지 않은 사용자는 그 건을 볼 수 없다."""

from tests.character_helpers import new_player
from tests.guild_helpers import join_with_code, new_guild
from tests.review_helpers import new_prepared, pending_review, request_review


def received(client, headers, **params):
    return client.get("/me/review-requests", params=params, headers=headers)


def test_us07_api036_lists_requests_sent_to_me(client):
    sid, _, leader_id, leader_headers = pending_review(client)

    res = received(client, leader_headers)

    assert res.status_code == 200
    body = res.json()
    assert body["nextCursor"] is None
    [item] = body["items"]
    assert item["submissionId"] == sid
    assert item["requester"]["nickname"] == "플레이어"
    assert item["exerciseCode"] == "SQUAT"
    assert item["countedReps"] == 30
    assert item["requestedAt"]


def test_us07_api036_others_do_not_see_it(client):
    _, requester, _, _ = pending_review(client)
    _, stranger = new_player(client)

    assert received(client, stranger).json()["items"] == []
    assert received(client, requester).json()["items"] == []  # 신청자에게 온 요청이 아님


def test_us07_api036_pending_default_hides_processed_but_all_shows(client):
    sid, requester, _, leader_headers = pending_review(client)
    version = client.get(f"/submissions/{sid}", headers=requester).json()["version"]
    client.post(f"/submissions/{sid}/cancel", headers=requester | {"If-Match": f'"{version}"'})

    assert received(client, leader_headers).json()["items"] == []
    assert [i["submissionId"] for i in received(client, leader_headers, status="ALL").json()["items"]] == [sid]


def test_us07_api036_paginates_newest_first(client):
    guild_id, leader_id, leader_headers = new_guild(client)
    sids = []
    for _ in range(3):
        _, member = join_with_code(client, guild_id, leader_headers)
        sid, _ = new_prepared(client, confidence=0.82, headers=member)
        assert request_review(client, sid, member, leader_id).status_code == 201
        sids.append(sid)

    first = received(client, leader_headers, limit=2).json()
    second = received(client, leader_headers, limit=2, cursor=first["nextCursor"]).json()

    assert [i["submissionId"] for i in first["items"]] == [sids[2], sids[1]]
    assert [i["submissionId"] for i in second["items"]] == [sids[0]]
    assert second["nextCursor"] is None


def test_us07_api036_rejects_bad_query(client):
    _, headers = new_player(client)
    assert received(client, headers, status="DONE").status_code == 400
    assert received(client, headers, limit=51).status_code == 400
    assert received(client, headers, cursor="not-a-cursor").status_code == 400


def test_us07_api036_requires_login(client):
    assert client.get("/me/review-requests").status_code == 401
