"""운동 제출건 상태값과 계산 상수.

상태 이름은 docs/domain/03-rules-states-llm.md 3-2, docs/DATA-MODEL.md '상태값'과 같다.
"""

from enum import StrEnum


class SubmissionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PREPARED = "PREPARED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REWARDED = "REWARDED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"
    REVOKED = "REVOKED"  # MVP에서 쓰지 않음 (F-07 제외, PRD v1.0 6절)


# 운동 종류 값 표기는 미정 (DATA-MODEL.md '아직 정하지 못한 것') — 팀 확인 필요
EXERCISE_SQUAT = "SQUAT"

# 타격 단위: 스쿼트 1회 = 1타 (user-flows.md 4단계, 03 R9)
HIT_UNIT = {EXERCISE_SQUAT: 1}
