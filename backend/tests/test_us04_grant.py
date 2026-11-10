"""API-041 보상·피해 1회 반영 — 노션 '전운시 API 명세서' API-041, backlog US-04 보상을 한 번만 반영.

피해는 던전·보스 모델이 없어 결과에만 담는다 (임시). 능력치 경험치는 반영하지 않는다 (모델 미정).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.modules.reward.models import Item, RewardLedger
from app.modules.submission.models import WorkoutSubmission
from tests.reward_helpers import approved_submission, grant
from tests.submission_helpers import new_submission, prepare


def _my_character(client, headers):
    return client.get("/characters/me", headers=headers).json()


def test_us04_grant_applies_snapshot_once_and_rewards(client, db):
    """(정상) APPROVED 건을 지급하면 REWARDED, 경험치·아이템이 스냅샷 값만큼 한 번 늘어난다."""
    submission_id, headers = approved_submission(client, db, counted=30)

    res = grant(client, submission_id)

    assert res.status_code == 200
    body = res.json()
    assert body["submissionId"] == submission_id
    assert body["alreadyGranted"] is False
    assert body["applied"]["exp"] == 150
    assert body["applied"]["damage"] == {"targetType": None, "targetId": None, "amount": 900}
    assert len(body["applied"]["items"]) == 1
    assert body["applied"]["items"][0]["status"] == "LOCKED"
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    db.refresh(saved)
    assert saved.status == "REWARDED"
    assert saved.version == 3  # 제출 0 → 스냅샷 1 → 승인 2 → 지급 3
    # 경험치는 캐릭터에 더해지고, 24시간 동안은 '확정 대기'
    me = _my_character(client, headers)
    assert me["exp"] == {"confirmed": 0, "pending": 150}
    assert me["lockedItemCount"] == 1


def test_us04_same_request_twice_returns_first_result(client, db):
    """(실패·거절) 같은 지급 요청이 두 번 오면 두 번째는 첫 결과를 돌려주고 다시 늘지 않는다."""
    submission_id, headers = approved_submission(client, db)
    key = str(uuid.uuid4())

    first = grant(client, submission_id, key).json()
    again = grant(client, submission_id, key)

    assert again.status_code == 200
    assert again.json() == first | {"alreadyGranted": True}
    assert _my_character(client, headers)["exp"]["pending"] == 150
    assert db.query(Item).count() == 1
    assert db.query(RewardLedger).count() == 1


def test_us04_other_request_after_grant_is_409(client, db):
    submission_id, headers = approved_submission(client, db)
    grant(client, submission_id)

    res = grant(client, submission_id)

    assert res.status_code == 409
    assert res.json()["code"] == "ALREADY_REWARDED"
    assert _my_character(client, headers)["exp"]["pending"] == 150


def test_us04_concurrent_grants_apply_once(client, db):
    """같은 키로 동시에 와도 한 번만 반영된다 (멱등 키 + 행 잠금)."""
    submission_id, headers = approved_submission(client, db)
    key = str(uuid.uuid4())

    def call(_):
        return grant(TestClient(app), submission_id, key).json()["alreadyGranted"]

    with ThreadPoolExecutor(max_workers=5) as pool:
        already = sorted(pool.map(call, range(5)))

    assert already == [False, True, True, True, True]
    assert _my_character(client, headers)["exp"]["pending"] == 150
    assert db.query(Item).count() == 1


def test_us04_failure_in_middle_applies_nothing(client, db, monkeypatch):
    """(실패·거절) 지급 중 오류가 나면 APPROVED에 남고 아무것도 반영되지 않으며, 재시도가 성공할 때만 REWARDED."""
    from app.modules.reward import service

    submission_id, headers = approved_submission(client, db)
    original = service._result

    def boom(*args, **kwargs):
        raise RuntimeError("forced failure after writes")

    monkeypatch.setattr(service, "_result", boom)
    failing = TestClient(app, raise_server_exceptions=False)
    assert grant(failing, submission_id).status_code == 500
    assert db.query(RewardLedger).count() == 0
    assert db.query(Item).count() == 0
    assert _my_character(client, headers)["exp"] == {"confirmed": 0, "pending": 0}
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "APPROVED"

    monkeypatch.setattr(service, "_result", original)
    assert grant(client, submission_id).status_code == 200
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "REWARDED"


def test_us04_not_approved_is_409(client, db):
    """(실패·거절) APPROVED가 아닌 건(PREPARED, CANCELED 등)의 지급 요청은 거부된다."""
    prepared_id, _ = new_submission(client)
    prepare(client, prepared_id)
    canceled_id, _ = new_submission(client)
    db.get(WorkoutSubmission, uuid.UUID(canceled_id)).status = "CANCELED"
    db.commit()

    for submission_id in (prepared_id, canceled_id):
        res = grant(client, submission_id)
        assert res.status_code == 409
        assert res.json()["code"] == "INVALID_STATE"
    assert db.query(RewardLedger).count() == 0


def test_us04_no_character_is_409_then_grant_after_creating(client, db):
    submission_id, headers = approved_submission(client, db, character=False)

    res = grant(client, submission_id)

    assert res.status_code == 409
    assert res.json()["details"]["reason"] == "NO_CHARACTER"
    client.post("/characters", json={}, headers=headers)
    assert grant(client, submission_id).status_code == 200


def test_us04_damage_target_comes_from_session(client, db):
    from tests.character_helpers import new_player
    from tests.submission_helpers import submit, upload_chunks

    _, headers = new_player(client)
    target = str(uuid.uuid4())
    res = client.post(
        "/workout-sessions", json={"exerciseCode": "SQUAT", "target": {"type": "BOSS", "id": target}}, headers=headers
    )
    session_id = res.json()["sessionId"]
    upload_chunks(client, headers, session_id)
    submission_id = submit(client, headers, session_id).json()["submissionId"]
    client.post("/characters", json={}, headers=headers)
    prepare(client, submission_id)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "APPROVED"
    db.commit()

    damage = grant(client, submission_id).json()["applied"]["damage"]

    assert damage == {"targetType": "BOSS", "targetId": target, "amount": 900}


def test_us04_player_cannot_grant(client, db):
    """(권한) 지급은 시스템만 실행하고, 플레이어가 지급을 직접 요청하면 거부된다."""
    submission_id, headers = approved_submission(client, db)

    res = client.post(
        f"/internal/submissions/{submission_id}/grant", headers=headers | {"Idempotency-Key": str(uuid.uuid4())}
    )

    assert res.status_code == 401
    assert db.query(RewardLedger).count() == 0


def test_us04_unknown_submission_is_404(client):
    assert grant(client, str(uuid.uuid4())).status_code == 404


def test_us04_my_character_reads_exp_and_pending_at_same_time(client, db):
    """API-007이 캐릭터를 읽은 직후 다른 요청의 지급이 커밋돼도 confirmed가 음수가 되지 않는다.

    검토에서 재현한 문제의 회귀 테스트: 경험치와 확정 대기 경험치를 따로 읽던 때는 {-150, 150}이 나왔다.
    캐릭터를 읽는 SQL이 끝난 직후(같은 요청의 다음 SQL 전)에 다른 연결로 지급을 커밋해 그 상황을 만든다.
    """
    from sqlalchemy import event

    from app.core.db import engine

    submission_id, headers = approved_submission(client, db)
    state = {"done": False}

    def grant_right_after_character_read(conn, cursor, statement, params, context, executemany):
        if state["done"] or not statement.lstrip().upper().startswith("SELECT") or "FROM character" not in statement:
            return
        state["done"] = True
        assert grant(TestClient(app), submission_id).status_code == 200

    event.listen(engine, "after_cursor_execute", grant_right_after_character_read)
    try:
        exp = _my_character(client, headers)["exp"]
    finally:
        event.remove(engine, "after_cursor_execute", grant_right_after_character_read)

    assert state["done"]
    assert exp["confirmed"] >= 0
    # 지급 전 시점이든 후 시점이든 한 시점의 값이어야 한다
    assert exp in ({"confirmed": 0, "pending": 0}, {"confirmed": 0, "pending": 150})
    assert _my_character(client, headers)["exp"] == {"confirmed": 0, "pending": 150}
