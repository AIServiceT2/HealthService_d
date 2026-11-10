"""운동 세션 규칙. 다른 모듈은 이 파일의 함수로만 세션을 다룬다."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.modules.workout_session.catalog import EXERCISES, Exercise

KST = ZoneInfo("Asia/Seoul")  # 일일 상한 날짜는 KST (노션 API 명세서 공통 규칙)


def today_kst() -> date:
    return datetime.now(KST).date()


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
