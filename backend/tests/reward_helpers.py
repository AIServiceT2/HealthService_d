"""지급 API 테스트 공통 도구.

APPROVED로 바꾸는 API(API-033 자동 승인·API-038 확인자 승인)가 아직 없어 승인 상태만 DB에서 바꾼다.
제출(API-026)·스냅샷(API-031)·캐릭터 생성(API-006)은 실제 API로 한다.
"""

import uuid

from app.modules.submission.models import WorkoutSubmission
from tests.submission_helpers import TEST_INTERNAL_TOKEN, new_submission, prepare


def approved_submission(client, db, *, counted=30, headers=None, character=True) -> tuple[str, dict[str, str]]:
    submission_id, headers = new_submission(client, counted=counted, headers=headers)
    if character:
        client.post("/characters", json={}, headers=headers)  # 이미 있으면 409, 상관없음
    assert prepare(client, submission_id).status_code == 200
    saved = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    saved.status = "APPROVED"
    saved.version += 1
    db.commit()
    return submission_id, headers


def grant(client, submission_id: str, key: str | None = None):
    return client.post(
        f"/internal/submissions/{submission_id}/grant",
        headers={"X-Internal-Token": TEST_INTERNAL_TOKEN, "Idempotency-Key": key or str(uuid.uuid4())},
    )
