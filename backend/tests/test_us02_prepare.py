"""US-02 보상·타격 수 미리보기 — first-feature.md 2절 #1, #3.

보상 계산은 노션 API-031(POST /internal/submissions/{id}/snapshot)로 바뀌었다.
첫 기능의 POST /submissions/{id}/prepare와 응답의 snapshot.hit_count는 없어졌다.
"""

import uuid

from app.modules.snapshot import service
from app.modules.snapshot.models import SubmissionSnapshot
from tests.submission_helpers import new_submission, prepare


def _submitted_squat(client, counted_reps=30):
    # 제출건에 사용자·세션이 필수가 되어(API-026) 실제 제출 흐름으로 SUBMITTED 건을 만든다.
    # 상태 조회(API-028)가 본인만 되므로 로그인 헤더도 돌려준다
    return new_submission(client, counted=counted_reps)


def test_us02_ac1_submitted_squat_30_becomes_prepared_with_30_hits(client, db):
    """#1 (정상) SUBMITTED 건의 계산이 끝나면 PREPARED, 인정 렙 30회 스쿼트의 타격 수는 30."""
    submission_id, headers = _submitted_squat(client)

    res = prepare(client, submission_id)

    assert res.status_code == 200
    assert res.json()["hitCount"] == 30

    # 저장된 상태와 스냅샷도 같은 값이고, 조회는 상태를 바꾸지 않는다
    res = client.get(f"/submissions/{submission_id}", headers=headers)
    assert res.json()["status"] == "PREPARED"
    assert db.get(SubmissionSnapshot, uuid.UUID(submission_id)).hit_count == 30


def test_us02_ac3_calculation_failure_keeps_submitted_then_retry_succeeds(client, db, monkeypatch):
    """#3 (실패·거절) 계산 실패 시 SUBMITTED에 남고, 재시도해서 성공했을 때만 PREPARED."""
    submission_id, headers = _submitted_squat(client)

    def fail(*args, **kwargs):
        raise service.CalculationError("forced failure")

    monkeypatch.setattr(service, "calculate_hit_count", fail)
    res = prepare(client, submission_id)
    assert res.status_code == 500

    res = client.get(f"/submissions/{submission_id}", headers=headers)
    assert res.json()["status"] == "SUBMITTED"
    assert db.get(SubmissionSnapshot, uuid.UUID(submission_id)) is None

    monkeypatch.undo()
    res = prepare(client, submission_id)
    assert res.status_code == 200
    assert res.json()["hitCount"] == 30
    assert client.get(f"/submissions/{submission_id}", headers=headers).json()["status"] == "PREPARED"
