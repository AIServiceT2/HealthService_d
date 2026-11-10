"""API-029 내 제출 목록 — 노션 '전운시 API 명세서' API-029.

한 사용자의 제출건 여러 개는 시간대가 겹치면 409라서(API-026), 만든 뒤 DB에서 시작·끝 시각을 옮긴다.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.submission_helpers import new_submission


def _submissions_at(client, db, starts):
    """starts의 시각마다 제출건을 하나씩 만든다. (ids, 헤더)."""
    _, headers = new_player(client)
    ids = []
    for started in starts:
        submission_id, _ = new_submission(client, headers=headers)
        saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
        saved.started_at = started
        saved.ended_at = started + timedelta(minutes=10)
        db.commit()
        ids.append(submission_id)
    return ids, headers


def _now():
    return datetime.now(UTC).replace(microsecond=0)


def test_us01_api029_lists_own_submissions_newest_first(client, db):
    now = _now()
    ids, headers = _submissions_at(client, db, [now - timedelta(hours=3), now - timedelta(hours=1), now - timedelta(hours=2)])
    new_submission(client)  # 다른 사용자 건은 나오지 않는다

    res = client.get("/me/submissions", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert [i["id"] for i in body["items"]] == [ids[1], ids[2], ids[0]]
    assert body["nextCursor"] is None
    # 항목 형식은 API-028과 같다
    assert body["items"][0] == client.get(f"/submissions/{ids[1]}", headers=headers).json()


def test_us01_api029_status_filter(client, db):
    now = _now()
    ids, headers = _submissions_at(client, db, [now - timedelta(hours=2), now - timedelta(hours=1)])
    db.get(WorkoutSubmission, uuid.UUID(ids[0])).status = "REWARDED"
    db.commit()

    items = client.get("/me/submissions", params={"status": "REWARDED"}, headers=headers).json()["items"]

    assert [i["id"] for i in items] == [ids[0]]


def test_us01_api029_date_range_is_kst_and_inclusive(client, db):
    # KST 11-08 23:30 = UTC 11-08 14:30 / KST 11-09 00:30 = UTC 11-08 15:30 / KST 11-10 12:00
    starts = [
        datetime(2026, 11, 8, 14, 30, tzinfo=UTC),
        datetime(2026, 11, 8, 15, 30, tzinfo=UTC),
        datetime(2026, 11, 10, 3, 0, tzinfo=UTC),
    ]
    ids, headers = _submissions_at(client, db, starts)

    only_9th = client.get("/me/submissions", params={"from": "2026-11-09", "to": "2026-11-09"}, headers=headers)
    from_9th = client.get("/me/submissions", params={"from": "2026-11-09"}, headers=headers)
    to_8th = client.get("/me/submissions", params={"to": "2026-11-08"}, headers=headers)

    assert [i["id"] for i in only_9th.json()["items"]] == [ids[1]]
    assert [i["id"] for i in from_9th.json()["items"]] == [ids[2], ids[1]]
    assert [i["id"] for i in to_8th.json()["items"]] == [ids[0]]


def test_us01_api029_pages_with_cursor(client, db):
    now = _now()
    ids, headers = _submissions_at(client, db, [now - timedelta(hours=h) for h in range(1, 6)])

    seen, cursor = [], None
    for _ in range(5):
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        body = client.get("/me/submissions", params=params, headers=headers).json()
        seen += [i["id"] for i in body["items"]]
        cursor = body["nextCursor"]
        if cursor is None:
            break

    assert seen == ids  # 1시간 전이 가장 최신


def test_us01_api029_empty_list(client):
    _, headers = new_player(client)

    assert client.get("/me/submissions", headers=headers).json() == {"items": [], "nextCursor": None}


def test_us01_api029_invalid_query_is_400(client):
    _, headers = new_player(client)

    for params in [
        {"status": "DONE"},
        {"from": "2026-13-01"},
        {"from": "2026-11-10", "to": "2026-11-09"},
        {"limit": 0},
        {"limit": 51},
        {"cursor": "broken"},
    ]:
        res = client.get("/me/submissions", params=params, headers=headers)
        assert res.status_code == 400, params
        assert res.json()["code"] == "VALIDATION_FAILED"


def test_us01_api029_without_token_is_401(client):
    res = client.get("/me/submissions")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"
