"""전투·결과 API 테스트 공통 도구: 공략 대상을 고른 세션으로 지급 완료(REWARDED) 건을 만든다.

제출(API-026)·스냅샷(API-031)·지급(API-041)은 실제 API로 하고, 승인 상태만 DB로 바꾼다
(자동 승인 API-033은 무작위 동작 확인 결과가 필요해 여기서는 단순화).
"""

import uuid

from app.modules.submission.models import WorkoutSubmission
from tests.character_helpers import new_player
from tests.reward_helpers import grant
from tests.submission_helpers import prepare, submit, submit_body, upload_chunks


def rewarded(client, db, *, target: tuple[str, uuid.UUID] | None = None, counted: int = 30, headers=None):
    """(submission_id, 헤더). 같은 사용자 건을 여러 번 만들 수 있게 끝 시각을 시작 시각으로 당겨 둔다."""
    if headers is None:
        _, headers = new_player(client)
    body = {"exerciseCode": "SQUAT"}
    if target is not None:
        body["target"] = {"type": target[0], "id": str(target[1])}
    session_id = client.post("/workout-sessions", json=body, headers=headers).json()["sessionId"]
    upload_chunks(client, headers, session_id)
    res = submit(client, headers, session_id, submit_body(counted=counted))
    assert res.status_code == 202, res.json()
    submission_id = res.json()["submissionId"]
    client.post("/characters", json={}, headers=headers)  # 이미 있으면 409, 상관없음
    assert prepare(client, submission_id).status_code == 200
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.status = "APPROVED"
    db.commit()
    assert grant(client, submission_id).status_code == 200
    db.refresh(saved)
    saved.ended_at = saved.started_at  # 다음 제출과 시간대가 겹치지 않게
    db.commit()
    return submission_id, headers
