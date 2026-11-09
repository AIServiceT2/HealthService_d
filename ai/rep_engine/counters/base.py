"""종목 판정기 인터페이스와 등록부 (플러그인 구조)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from rep_engine.config import EngineConfig
from rep_engine.features.extractor import FrameFeatures
from rep_engine.schemas import RepEvent


class ExerciseCounter(ABC):
    """종목별 렙 판정기.

    스트리밍: 프레임 특징을 시각 순서대로 `update`에 넣으면 그 프레임에서 끝난 렙을 돌려준다.
    배치: `run`은 `update`를 반복 호출할 뿐이라 두 경로의 결과가 항상 같다.
    """

    @abstractmethod
    def update(self, features: FrameFeatures) -> list[RepEvent]:
        """프레임 하나를 처리하고, 이번 프레임에서 확정된 렙 목록을 돌려준다."""

    @property
    @abstractmethod
    def state(self) -> str:
        """현재 상태 이름 (실시간 UI용)."""

    @property
    @abstractmethod
    def current_angle(self) -> float | None:
        """마지막 유효 프레임의 판정 각도(도)."""

    @property
    @abstractmethod
    def accepted_count(self) -> int:
        """지금까지 인정된 렙 수."""

    def run(self, features: Iterable[FrameFeatures]) -> list[RepEvent]:
        """배치 처리 = 스트리밍 반복."""
        events: list[RepEvent] = []
        for f in features:
            events.extend(self.update(f))
        return events


CounterFactory = Callable[[EngineConfig], ExerciseCounter]
_REGISTRY: dict[str, CounterFactory] = {}


def register_counter(exercise_type: str, factory: CounterFactory) -> None:
    """종목 판정기를 등록한다 (예: `register_counter("SQUAT", SquatCounter.from_config)`)."""
    _REGISTRY[exercise_type] = factory


def make_counter(exercise_type: str, cfg: EngineConfig) -> ExerciseCounter:
    """등록된 판정기를 만든다. 없으면 KeyError."""
    if exercise_type not in _REGISTRY:
        raise KeyError(f"등록되지 않은 종목: {exercise_type}")
    return _REGISTRY[exercise_type](cfg)


def registered_exercises() -> list[str]:
    return sorted(_REGISTRY)
