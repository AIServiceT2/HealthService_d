"""LLM 글 생성 규칙 (노션 API-049~051, 03-rules-states-llm.md 3-4).

공통:
- 입력은 레벨마다 허용된 필드만 담는 함수(_l3_input 등)로 만든다. 닉네임·길드명·메모·관절 좌표 원본·
  얼굴 정보는 넣지 않는다 (PRD 7절, STACK.md '입력 데이터 계약').
- 출력은 규칙으로 검사하고, 실패하면 다시 만든다. MAX_ATTEMPTS번 실패하면 기본 문구를 저장한다.
- LLM 출력은 ai_* 필드에만 저장하고 상태·보상 수치를 바꾸지 않는다 (03 3-4 공통 원칙, US-02 (LLM)).
- DB 트랜잭션을 잡은 채 LLM 응답을 기다리지 않는다. 결과를 저장할 때 제출건 상태를 다시 검사한다
  (STACK.md '입력 데이터 계약과 재시도 계획').
"""

import json
import statistics
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
from app.modules.submission.models import RepEvent, WorkoutSubmission
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
    if rules.DIGITS.search(text) or rules.KOREAN_NUMBERS.search(text):
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


# ---- L4 자세 교정 코멘트 (API-050) ----


def _l4_input(submission: WorkoutSubmission, pose_summary: dict[str, dict]) -> dict[str, Any]:
    """L4에 보내는 것: 운동 종류·판정 기준·관절 각도 요약 통계만 (03 3-4, backlog US-02 (LLM)).

    - 판정 기준(가동범위 수치)은 미정이라 None (노션 API-018 criteria.kneeAngleMax)
    - 미인정 사유는 제출건에 저장하는 곳이 아직 없어 넣지 않았다 [팀 확인 필요]
    - 보상 수치·메모·관절 좌표 원본·얼굴 정보·닉네임·길드명은 넣지 않는다
    """
    return {
        "exerciseName": EXERCISES[submission.exercise_code].name,
        "criteria": {"kneeAngleMax": None},
        "poseSummary": pose_summary,
    }


def is_valid_form_tip(text: str) -> bool:
    """숫자(수치는 결과 카드에만, 03 3-4)나 진단·처방처럼 들리는 표현이 있으면 탈락 (backlog US-05)."""
    if rules.DIGITS.search(text):
        return False
    return not any(word in text for word in rules.MEDICAL_WORDS)


def generate_form_tip(
    db: Session, client: LLMClient, submission_id: uuid.UUID, pose_summary: dict[str, dict]
) -> Generated:
    """L4 자세 교정 코멘트를 만들어 ai_form_tip에 저장한다 (노션 API-050).

    이미 LLM이 만든 코멘트(기본 문구가 아닌 것)가 있으면 다시 부르지 않는다 [제안].
    """
    submission = _read(db, submission_id)
    if submission.ai_form_tip and submission.ai_form_tip != rules.FALLBACK_FORM_TIP:
        return Generated("L4", submission.ai_form_tip, False)
    payload = _l4_input(submission, pose_summary)
    db.rollback()

    try:
        text = _generate(client, "L4", payload, is_valid_form_tip)
    except LLMRateLimited:
        _save(db, submission_id, lambda s: setattr(s, "ai_form_tip", rules.FALLBACK_FORM_TIP))
        raise RateLimited(Generated("L4", rules.FALLBACK_FORM_TIP, True)) from None

    result = Generated("L4", text, False) if text else Generated("L4", rules.FALLBACK_FORM_TIP, True)
    _save(db, submission_id, lambda s: setattr(s, "ai_form_tip", result.text))
    return result


# ---- L1 기록 요약·L2 이상치 설명 (API-051) ----


@dataclass(frozen=True)
class RepStats:
    counted: int
    uncounted: int
    intervals: list[tuple[int, float]]  # (뒤 렙 번호, 앞 렙과의 간격 초)

    def interval_summary(self) -> dict[str, float] | None:
        if not self.intervals:
            return None
        values = [v for _, v in self.intervals]
        return {
            "avg": round(statistics.fmean(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "std": round(statistics.pstdev(values), 2),
        }


def _rep_stats(db: Session, submission_id: uuid.UUID) -> RepStats:
    reps = list(
        db.scalars(select(RepEvent).where(RepEvent.submission_id == submission_id).order_by(RepEvent.rep_no))
    )
    intervals = [
        (b.rep_no, (b.ts - a.ts).total_seconds()) for a, b in zip(reps, reps[1:], strict=False)
    ]
    counted = sum(1 for r in reps if r.counted)
    return RepStats(counted, len(reps) - counted, intervals)


def find_anomalies(stats: RepStats) -> list[dict[str, Any]]:
    """규칙 검사로 이상치 종류와 렙 번호를 찾는다. LLM은 이 결과를 설명만 한다 (03 3-4 L2)."""
    found: list[dict[str, Any]] = []
    fast = [no for no, sec in stats.intervals if sec < rules.MIN_REP_INTERVAL_SEC]
    if fast:
        found.append({"type": "TEMPO_TOO_FAST", "repNos": fast})
    values = [sec for _, sec in stats.intervals]
    if len(values) + 1 >= rules.UNIFORM_TEMPO_MIN_REPS and statistics.pstdev(values) < rules.UNIFORM_TEMPO_STD_SEC:
        found.append({"type": "UNIFORM_TEMPO", "repNos": []})
    return found


def _l1_input(submission: WorkoutSubmission, stats: RepStats) -> dict[str, Any]:
    """L1에 보내는 것: 운동 종류·인정/미인정 렙 수·렙 간격 통계 (03 3-4 L1, 노션 API-051).

    닉네임·길드명·메모·관절 좌표 원본은 넣지 않는다. 렙 간격은 통계로만 보낸다.
    메모 입력은 아직 없다 (DATA-MODEL.md '아직 정하지 못한 것').
    """
    return {
        "exerciseName": EXERCISES[submission.exercise_code].name,
        "countedReps": stats.counted,
        "uncountedReps": stats.uncounted,
        "repIntervalSec": stats.interval_summary(),
    }


def _l2_input(anomaly: dict[str, Any], stats: RepStats) -> dict[str, Any]:
    """L2에 보내는 것: 규칙 검사 결과(종류·렙 번호)와 렙 간격 통계만 (03 3-4 L2)."""
    return {"anomalyType": anomaly["type"], "repNos": anomaly["repNos"], "repIntervalSec": stats.interval_summary()}


def _fallback_summary(payload: dict[str, Any]) -> str:
    """LLM이 실패하면 입력값으로 만든 기본 문장 (03 3-4 L1)."""
    text = f"{payload['exerciseName']} 인정 {payload['countedReps']}회, 미인정 {payload['uncountedReps']}회."
    if payload["repIntervalSec"]:
        text += f" 렙 간격 평균 {payload['repIntervalSec']['avg']}초."
    return text


def _any_text(text: str) -> bool:
    """L1·L2는 숫자(렙 수·간격)를 써도 된다. 길이·빈 값 검사(_generate)만 한다."""
    return True


def generate_review_summary(db: Session, client: LLMClient, submission_id: uuid.UUID) -> dict[str, Any]:
    """L1 요약을 ai_summary에, L2 이상치 설명을 ai_flags(JSON 배열)에 저장한다 (노션 API-051).

    - 확인 화면(API-034·037)에 표시만 하고 상태를 바꾸지 않는다 (US-07 (LLM))
    - 자동 승인 건에도 만들지는 미정 → 상태로 막지 않고 호출한 쪽이 정한다 (노션 API-051)
    - 이미 저장된 값이 있어도 다시 만든다 (요청 시점의 렙 기록으로 새로 요약) [제안]
    """
    submission = _read(db, submission_id)
    stats = _rep_stats(db, submission_id)
    l1 = _l1_input(submission, stats)
    found = find_anomalies(stats)
    db.rollback()

    try:
        summary = _generate(client, "L1", l1, _any_text) or _fallback_summary(l1)
        anomalies = [
            {
                **a,
                "description": _generate(client, "L2", _l2_input(a, stats), _any_text)
                or rules.FALLBACK_ANOMALY_DESCRIPTIONS[a["type"]],
            }
            for a in found
        ]
    except LLMRateLimited:
        summary = _fallback_summary(l1)
        anomalies = [{**a, "description": rules.FALLBACK_ANOMALY_DESCRIPTIONS[a["type"]]} for a in found]
        _save_review_summary(db, submission_id, summary, anomalies)
        raise RateLimited(Generated("L1", summary, True)) from None

    _save_review_summary(db, submission_id, summary, anomalies)
    return {"summary": summary, "anomalies": anomalies}


def _save_review_summary(
    db: Session, submission_id: uuid.UUID, summary: str, anomalies: list[dict[str, Any]]
) -> None:
    def apply(s: WorkoutSubmission) -> None:
        s.ai_summary = summary
        s.ai_flags = json.dumps(anomalies, ensure_ascii=False)

    _save(db, submission_id, apply)
