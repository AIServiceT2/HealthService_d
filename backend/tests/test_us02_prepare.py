"""US-02 보상·타격 수 미리보기 — first-feature.md 2절 #1, #3."""

from app.modules.submission import service
from app.modules.submission.constants import EXERCISE_SQUAT, SubmissionStatus
from app.modules.submission.models import WorkoutSubmission


def _submitted_squat(db, counted_reps=30):
    submission = WorkoutSubmission(
        status=SubmissionStatus.SUBMITTED,
        exercise_type=EXERCISE_SQUAT,
        counted_reps=counted_reps,
    )
    db.add(submission)
    db.commit()
    return submission.id


def test_us02_ac1_submitted_squat_30_becomes_prepared_with_30_hits(client, db):
    """#1 (정상) SUBMITTED 건의 계산이 끝나면 PREPARED, 인정 렙 30회 스쿼트의 타격 수는 30."""
    submission_id = _submitted_squat(db)

    res = client.post(f"/submissions/{submission_id}/prepare")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "PREPARED"
    assert body["snapshot"]["hit_count"] == 30

    # 미리보기 조회에서도 같은 값이 보이고, 조회는 상태를 바꾸지 않는다
    res = client.get(f"/submissions/{submission_id}")
    assert res.json()["status"] == "PREPARED"
    assert res.json()["snapshot"]["hit_count"] == 30


def test_us02_ac3_calculation_failure_keeps_submitted_then_retry_succeeds(client, db, monkeypatch):
    """#3 (실패·거절) 계산 실패 시 SUBMITTED에 남고, 재시도해서 성공했을 때만 PREPARED."""
    submission_id = _submitted_squat(db)

    def fail(*args, **kwargs):
        raise service.CalculationError("forced failure")

    monkeypatch.setattr(service, "calculate_hit_count", fail)
    res = client.post(f"/submissions/{submission_id}/prepare")
    assert res.status_code == 500

    res = client.get(f"/submissions/{submission_id}")
    assert res.json()["status"] == "SUBMITTED"
    assert res.json()["snapshot"] is None

    monkeypatch.undo()
    res = client.post(f"/submissions/{submission_id}/prepare")
    assert res.status_code == 200
    assert res.json()["status"] == "PREPARED"
    assert res.json()["snapshot"]["hit_count"] == 30
