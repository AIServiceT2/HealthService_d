"""API-047 결과 카드·서사·교정 코멘트 조회 — 노션 '전운시 API 명세서' API-047, backlog US-05.

LLM 연결 전이라 서사·교정 코멘트는 기본 문구(DESIGN.md 5절 제안)와 isFallback=true.
"""

import uuid

from app.modules.result.service import FALLBACK_FORM_COMMENT, FALLBACK_NARRATIVE
from app.modules.submission.models import DailyCapReservation, WorkoutSubmission
from tests.battle_helpers import rewarded
from tests.character_helpers import new_player
from tests.reward_helpers import approved_submission, grant
from tests.submission_helpers import new_submission, prepare


def _result(client, submission_id, headers):
    return client.get(f"/submissions/{submission_id}/result", headers=headers)


def test_us05_result_card_with_fallback_texts(client, db):
    submission_id, headers = rewarded(client, db, counted=30)

    res = _result(client, submission_id, headers)

    assert res.status_code == 200
    body = res.json()
    card = body["card"]
    assert card["exerciseCode"] == "SQUAT"
    assert card["countedReps"] == 30
    assert card["hitCount"] == 30
    assert card["exp"] == 150
    assert card["totalDamage"] == 900
    assert [d["status"] for d in card["drops"]] == ["LOCKED"]
    assert card["dailyCapExceeded"] is False
    # 지급 결과와 같은 값
    granted = client.get("/me/rewards", headers=headers).json()["items"][0]
    assert card["rewardedAt"] == granted["rewardedAt"]
    assert card["drops"][0]["itemId"] == granted["items"][0]["itemId"]
    assert body["narrative"] == {"level": "L3", "text": FALLBACK_NARRATIVE, "isFallback": True}
    assert body["formComment"] == {"level": "L4", "text": FALLBACK_FORM_COMMENT, "isFallback": True}


def test_us05_saved_llm_texts_are_shown_and_numbers_unchanged(client, db):
    """(LLM) 서사·코멘트가 있어도 결과 카드 수치는 그대로다."""
    submission_id, headers = rewarded(client, db)
    before = _result(client, submission_id, headers).json()["card"]
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.ai_story = "충격파가 적을 흔들었다."
    saved.ai_form_tip = "내려갈 때 무릎이 발끝 방향을 향하게 해 보세요."
    db.commit()

    body = _result(client, submission_id, headers).json()

    assert body["narrative"] == {"level": "L3", "text": "충격파가 적을 흔들었다.", "isFallback": False}
    assert body["formComment"]["isFallback"] is False
    assert body["card"] == before


def test_us05_daily_cap_exceeded_card(client, db):
    """(실패·거절) 일일 상한 초과로 타격 0이면 '일일 상한 초과' 카드 (dailyCapExceeded=true)."""
    submission_id, headers = new_submission(client)
    client.post("/characters", json={}, headers=headers)
    db.get(DailyCapReservation, uuid.UUID(submission_id)).amount = 0
    db.commit()
    prepare(client, submission_id)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "APPROVED"
    db.commit()
    grant(client, submission_id)

    card = _result(client, submission_id, headers).json()["card"]

    assert card["dailyCapExceeded"] is True
    assert card["hitCount"] == 0
    assert card["countedReps"] == 30  # 운동 기록은 남는다
    assert card["drops"] == []


def test_us05_result_does_not_change_state(client, db):
    submission_id, headers = rewarded(client, db)
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    version = saved.version

    for _ in range(2):
        _result(client, submission_id, headers)

    db.refresh(saved)
    assert (saved.status, saved.version) == ("REWARDED", version)


def test_us05_not_rewarded_is_409(client, db):
    """(실패·거절) REWARDED가 아닌 건(PREPARED, APPROVED 등)은 결과를 열 수 없다."""
    prepared_id, prepared_headers = new_submission(client)
    prepare(client, prepared_id)
    approved_id, approved_headers = approved_submission(client, db)

    for submission_id, headers in ((prepared_id, prepared_headers), (approved_id, approved_headers)):
        res = _result(client, submission_id, headers)
        assert res.status_code == 409
        assert res.json()["code"] == "INVALID_STATE"


def test_us05_other_user_is_403(client, db):
    """(권한) 결과 카드·서사·교정 코멘트는 본인에게만 보인다."""
    submission_id, _ = rewarded(client, db)
    _, other = new_player(client)

    res = _result(client, submission_id, other)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_us05_unknown_is_404_and_needs_token(client):
    _, headers = new_player(client)

    assert _result(client, uuid.uuid4(), headers).status_code == 404
    assert client.get(f"/submissions/{uuid.uuid4()}/result").status_code == 401


def test_us05_llm_failure_fallback_saved_is_shown_as_fallback(client, db):
    """LLM 생성(API-049·050)이 2번 실패해 기본 문구를 저장했으면 결과 카드에서도 isFallback=true (US-05)."""
    from app.modules.llm.rules import FALLBACK_FORM_TIP
    from app.modules.snapshot.rules import FALLBACK_NARRATIVE as STORED_NARRATIVE

    submission_id, headers = rewarded(client, db)
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.ai_story = STORED_NARRATIVE
    saved.ai_form_tip = FALLBACK_FORM_TIP
    db.commit()

    body = _result(client, submission_id, headers).json()

    assert body["narrative"] == {"level": "L3", "text": FALLBACK_NARRATIVE, "isFallback": True}
    assert body["formComment"] == {"level": "L4", "text": FALLBACK_FORM_COMMENT, "isFallback": True}
