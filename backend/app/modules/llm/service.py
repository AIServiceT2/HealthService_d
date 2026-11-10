"""LLM 글 생성 규칙 (노션 API-049~051, 03-rules-states-llm.md 3-4).

공통:
- 입력은 레벨마다 허용된 필드만 담는 함수(_l3_input 등)로 만든다. 닉네임·길드명·메모·관절 좌표 원본·
  얼굴 정보는 넣지 않는다 (PRD 7절, STACK.md '입력 데이터 계약').
- 출력은 규칙으로 검사하고, 실패하면 다시 만든다. MAX_ATTEMPTS번 실패하면 기본 문구를 저장한다.
- LLM 출력은 ai_* 필드에만 저장하고 상태·보상 수치를 바꾸지 않는다 (03 3-4 공통 원칙, US-02 (LLM)).
- DB 트랜잭션을 잡은 채 LLM 응답을 기다리지 않는다. 결과를 저장할 때 제출건 상태를 다시 검사한다
  (STACK.md '입력 데이터 계약과 재시도 계획').
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.llm import rules
from app.modules.llm.client import LLMClient, LLMError, LLMRateLimited
from app.modules.snapshot.rules import FALLBACK_NARRATIVE
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission
from app.modules.workout_session.catalog import EXERCISES


class SubmissionNotFound(Exception):
    pass


class InvalidState(Exception):
    pass


class RateLimited(Exception):
    """호출 한도 초과. 기본 문구는 저장했고, 호출한 쪽이 나중에 다시 부르면 덮어쓴다."""

    def __init__(self, result: "Generated"):
        super().__init__("RATE_LIMITED")
        self.result = result


# 글을 만들 수 있는 상태 [제안·팀 확인 필요]: 보상이 계산된 뒤(PREPARED)부터 지급까지.
# 계산 전(SUBMITTED)·취소·반려·종료 건은 보여 줄 곳이 없어 만들지 않는다
GENERATABLE = (
    SubmissionStatus.PREPARED,
    SubmissionStatus.PENDING_REVIEW,
    SubmissionStatus.APPROVED,
    SubmissionStatus.REWARDED,
)


@dataclass(frozen=True)
class Generated:
    level: str
    text: str
    is_fallback: bool


def _read(db: Session, submission_id: uuid.UUID) -> WorkoutSubmission:
    submission = db.get(WorkoutSubmission, submission_id)
    if submission is None:
        raise SubmissionNotFound(str(submission_id))
    if submission.status not in GENERATABLE:
        raise InvalidState(submission.status)
    return submission


def _generate(
    client: LLMClient,
    level: str,
    payload: dict[str, Any],
    is_valid: Callable[[str], bool],
) -> str | None:
    """검사를 통과한 출력을 돌려준다. MAX_ATTEMPTS번 모두 실패하면 None. 한도 초과는 바로 올린다."""
    for _ in range(rules.MAX_ATTEMPTS):
        try:
            text = client.generate(level, payload).strip()
        except LLMRateLimited:
            raise
        except LLMError:
            continue
        if text and len(text) <= rules.MAX_OUTPUT_LENGTH and is_valid(text):
            return text
    return None


def _save(
    db: Session, submission_id: uuid.UUID, apply: Callable[[WorkoutSubmission], None]
) -> None:
    """제출건 행을 잠그고 상태를 다시 검사한 뒤 ai_* 필드만 바꾼다."""
    try:
        submission = db.scalars(
            select(WorkoutSubmission)
            .where(WorkoutSubmission.id == submission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        if submission.status not in GENERATABLE:
            # LLM을 기다리는 동안 취소된 건: 늦게 온 결과를 저장하지 않는다
            raise InvalidState(submission.status)
        apply(submission)
        db.commit()
    except Exception:
        db.rollback()
        raise


# ---- L3 전투 서사 (API-049) ----


def _l3_input(submission: WorkoutSubmission) -> dict[str, Any]:
    """L3에 보내는 것: 스킬명·운동 종류·적 이름·약점 적중 여부만 (03 3-4, backlog US-02 (LLM)).

    - 적 이름: 공략 대상(던전 적 / 주간 보스) 모델이 아직 없어 None (PRD 미정 표)
    - 약점: 약점 배율은 MVP 제외라 항상 false (mvp-scope.md 제외 표)
    """
    return {
        "skillName": rules.SKILL_BY_EXERCISE[submission.exercise_code],
        "exerciseName": EXERCISES[submission.exercise_code].name,
        "enemyName": None,
        "weaknessHit": False,
    }


def is_valid_narrative(text: str, skill_name: str) -> bool:
    """숫자·다른 스킬명·아이템명이 있으면 탈락 (backlog US-05 (실패·거절))."""
    if rules.DIGITS.search(text):
        return False
    other_skills = [s for s in rules.SKILL_BY_EXERCISE.values() if s != skill_name]
    return not any(name in text for name in (*other_skills, *rules.ITEM_NAMES))


def generate_narrative(db: Session, client: LLMClient, submission_id: uuid.UUID) -> Generated:
    """L3 전투 서사를 만들어 ai_story에 저장한다 (노션 API-049).

    이미 LLM이 만든 서사(기본 문구가 아닌 것)가 있으면 다시 부르지 않고 그대로 돌려준다
    (같은 요청을 다시 보내도 결과가 같고 호출 비용이 들지 않음) [제안].
    """
    submission = _read(db, submission_id)
    if submission.ai_story and submission.ai_story != FALLBACK_NARRATIVE:
        return Generated("L3", submission.ai_story, False)
    payload = _l3_input(submission)
    db.rollback()  # 읽기 트랜잭션을 닫고 LLM을 기다린다

    try:
        text = _generate(
            client, "L3", payload, lambda t: is_valid_narrative(t, payload["skillName"])
        )
    except LLMRateLimited:
        _save(db, submission_id, lambda s: setattr(s, "ai_story", FALLBACK_NARRATIVE))
        raise RateLimited(Generated("L3", FALLBACK_NARRATIVE, True)) from None

    result = Generated("L3", text, False) if text else Generated("L3", FALLBACK_NARRATIVE, True)
    _save(db, submission_id, lambda s: setattr(s, "ai_story", result.text))
    return result
