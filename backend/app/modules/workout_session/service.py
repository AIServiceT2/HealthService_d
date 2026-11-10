"""운동 세션 규칙. 다른 모듈은 이 파일의 함수로만 세션을 다룬다."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.workout_session.catalog import EXERCISES, Exercise
from app.modules.workout_session.models import SessionStatus, WorkoutSession

KST = ZoneInfo("Asia/Seoul")  # 일일 상한 날짜는 KST (노션 API 명세서 공통 규칙)


def today_kst() -> date:
    return datetime.now(KST).date()


def _now() -> datetime:
    return datetime.now(UTC)


def _validation_failed(reason: str) -> AppError:
    return AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": reason})


# ---- 일일 상한 (API-019) ----


@dataclass(frozen=True)
class DailyCap:
    exercise: Exercise
    reserved: int

    @property
    def remaining(self) -> int:
        return max(self.exercise.daily_cap - self.reserved, 0)


def _reserved_today(user_id: uuid.UUID, exercise_code: str, day: date) -> int:
    """그날(KST) 해제되지 않은 상한 예약 합계 (노션 API-019).

    예약(DAILY_CAP_RESERVATION)은 제출(API-026) 때 만들어지는데 제출이 아직 없어 항상 0이다.
    제출을 구현할 때 이 함수만 실제 합계로 바꾼다.
    """
    return 0


def daily_caps(user_id: uuid.UUID, day: date | None = None) -> list[DailyCap]:
    day = day or today_kst()
    return [DailyCap(e, _reserved_today(user_id, e.code, day)) for e in EXERCISES.values()]


def daily_cap(user_id: uuid.UUID, exercise_code: str, day: date | None = None) -> DailyCap:
    day = day or today_kst()
    exercise = EXERCISES[exercise_code]
    return DailyCap(exercise, _reserved_today(user_id, exercise_code, day))


# ---- 세션 시작 (API-020) ----

# 무작위 동작 이름은 ai/ 엔진(ai/rep_engine/schemas.py LivenessAction)과 같게 둔다
LIVENESS_ACTIONS = ("RAISE_LEFT_HAND", "RAISE_RIGHT_HAND", "RAISE_BOTH_HANDS")
# 동작 확인 제한 시간 (노션 API-020 예시 값) [가정]. 판정 기준·실패 정책은 미정 (PRD 미정 표)
LIVENESS_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Goal:
    reps: int
    sets: int


@dataclass(frozen=True)
class Target:
    type: str
    id: uuid.UUID


def start_session(
    db: Session,
    user_id: uuid.UUID,
    exercise_code: str,
    goal: Goal | None,
    target: Target | None,
) -> tuple[WorkoutSession, DailyCap]:
    """세션을 ACTIVE로 만들고 무작위 동작 1개를 발급한다 (노션 API-020).

    일일 상한이 다 찼을 때 세션을 막을지는 미정(노션 'DAILY_CAP_EXCEEDED 경고용, 차단 여부 미정')이라
    막지 않고 남은 상한만 돌려준다.
    """
    if exercise_code not in EXERCISES:
        raise _validation_failed("UNKNOWN_EXERCISE")

    now = _now()
    session = WorkoutSession(
        user_id=user_id,
        exercise_code=exercise_code,
        status=SessionStatus.ACTIVE,
        goal_reps=goal.reps if goal else None,
        goal_sets=goal.sets if goal else None,
        target_type=target.type if target else None,
        target_id=target.id if target else None,
        liveness_challenge_id=uuid.uuid4(),
        liveness_action=secrets.choice(LIVENESS_ACTIONS),
        liveness_issued_at=now,
        started_at=now,
    )
    db.add(session)
    db.commit()
    return session, daily_cap(user_id, exercise_code)


# ---- 본인 세션 확인 (API-021~027 공통) ----


def get_owned_session(
    db: Session, user_id: uuid.UUID, session_id: uuid.UUID, *, lock: bool = False
) -> WorkoutSession:
    """세션이 없으면 404, 남의 세션이면 403 (노션 API-025 Error Code).

    lock=True면 행을 잠가, 상태를 바꾸는 요청이 동시에 와도 하나씩 처리한다.
    """
    stmt = select(WorkoutSession).where(WorkoutSession.id == session_id)
    if lock:
        stmt = stmt.with_for_update()
    session = db.scalars(stmt).one_or_none()
    if session is None:
        raise AppError(404, "NOT_FOUND", "세션을 찾을 수 없습니다.")
    if session.user_id != user_id:
        raise AppError(403, "FORBIDDEN", "본인 세션만 조회할 수 있습니다.")
    return session


def _invalid_state(message: str) -> AppError:
    return AppError(409, "INVALID_STATE", message)


# ---- 무작위 동작 확인 (API-021) ----


def submit_liveness(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    challenge_id: uuid.UUID,
    detected_action: str,
    now: datetime | None = None,
) -> bool:
    """앱이 판정한 무작위 동작 결과를 받아 liveness_passed에 저장한다 (노션 API-021).

    통과 조건 [가정]: 발급한 동작과 같고, 서버가 받은 시각이 발급 후 제한 시간 안.
    - 제한 시간은 앱이 보낸 detectedAt이 아니라 서버 시각으로 잰다 (앱 시계는 바꿀 수 있음).
    - score는 기준값이 미정이라 판정에 쓰지 않는다 (PRD 미정 표 '무작위 동작 확인 실패 시 처리').
    - 실패해도 다시 시도할 수 없다. 재시작/제출 허용 정책이 미정이라 한 번만 받는다.
    """
    now = now or _now()
    try:
        session = get_owned_session(db, user_id, session_id, lock=True)
        if session.status != SessionStatus.ACTIVE or session.liveness_passed is not None:
            raise _invalid_state("종료된 세션이거나 이미 확인을 끝냈습니다.")
        if challenge_id != session.liveness_challenge_id:
            raise _validation_failed("CHALLENGE_MISMATCH")

        deadline = session.liveness_issued_at + timedelta(seconds=LIVENESS_TIMEOUT_SECONDS)
        passed = detected_action == session.liveness_action and now <= deadline
        session.liveness_passed = passed
        db.commit()
    except Exception:
        db.rollback()
        raise
    return passed
