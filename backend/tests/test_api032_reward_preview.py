"""API-032 보상·타격 수 미리보기 — 노션 '전운시 API 명세서' API-032 (US-02).

서사(L3)는 LLM 연결 전이라 기본 문구와 isFallback=true. 기본 문구는 제안값 (snapshot/rules.py).
"""

import uuid

from app.modules.snapshot import rules
from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.submission_helpers import new_submission, prepare


def _preview(client, submission_id, headers):
    return client.get(f"/submissions/{submission_id}/reward-preview", headers=headers)


def test_us02_api032_prepared_shows_snapshot_and_fallback_narrative(client):
    submission_id, headers = new_submission(client, counted=30)
    prepare(client, submission_id)

    res = _preview(client, submission_id, headers)

    assert res.status_code == 200
    assert res.json() == {
        "status": "PREPARED",
        "snapshot": {
            "catalogVersion": "cat_2026-11-01",
            "hitCount": 30,
            "exp": 150,
            "totalDamage": 900,
            "weaknessMultiplier": 1.0,
            "dropCount": 1,
        },
        "narrative": {"level": "L3", "text": rules.FALLBACK_NARRATIVE, "isFallback": True},
    }


def test_us02_api032_before_snapshot_is_202_with_retry(client):
    submission_id, headers = new_submission(client)

    res = _preview(client, submission_id, headers)

    assert res.status_code == 202
    assert res.json() == {"status": "SUBMITTED", "retryAfterSec": 2}


def test_us02_api032_preview_does_not_change_state(client, db):
    submission_id, headers = new_submission(client)
    prepare(client, submission_id)

    for _ in range(2):
        _preview(client, submission_id, headers)

    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    assert saved.status == "PREPARED"
    assert saved.version == 1


def test_us02_api032_saved_story_is_shown_without_fallback(client, db):
    """LLM 서사가 저장되어 있으면 그대로 보여 주고, 수치는 스냅샷 그대로 (backlog US-02 (LLM))."""
    submission_id, headers = new_submission(client)
    before = prepare(client, submission_id).json()
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).ai_story = "충격파가 적을 흔들었다."
    db.commit()

    body = _preview(client, submission_id, headers).json()

    assert body["narrative"] == {"level": "L3", "text": "충격파가 적을 흔들었다.", "isFallback": False}
    assert body["snapshot"]["hitCount"] == before["hitCount"]


def test_us02_api032_other_user_is_403(client):
    """보상 미리보기는 제출한 본인에게만 보인다 (backlog US-02 (권한))."""
    submission_id, _ = new_submission(client)
    prepare(client, submission_id)
    _, other = new_player(client)

    res = _preview(client, submission_id, other)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_us02_api032_unknown_is_404(client):
    _, headers = new_player(client)

    assert _preview(client, uuid.uuid4(), headers).status_code == 404


def test_us02_api032_ended_before_snapshot_is_409(client, db):
    submission_id, headers = new_submission(client)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "CANCELED"
    db.commit()

    res = _preview(client, submission_id, headers)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us02_api032_without_token_is_401(client):
    assert client.get(f"/submissions/{uuid.uuid4()}/reward-preview").status_code == 401
