"""다리를 번갈아 하는 종목(하이 니·마운틴 클라이머)의 렙 판정 (D-83, D-84).

다리마다 `FlexionCounter` 규칙(`flexion.py`)으로 굽혔다 펴기를 따로 판정한다. 판정 각도는 그 다리의
엉덩이 내각(어깨–엉덩이–무릎)이다. 다리 하나의 판정 결과는 바로 내보내지 않고,
**왼다리 1번 + 오른다리 1번을 묶어 1렙**으로 만든다 (요청자 결정, 2026-11-23).

- 두 다리가 모두 인정이어야 인정. 아니면 두 다리 사유 중 우선순위가 높은 것
  (OUT_OF_FRAME > TOO_FAST > SHALLOW_DEPTH)이 렙 사유가 된다.
- 짝 짓기: 다리 결과를 끝난 시각 순서로 본다. 대기 중인 다리가 없으면 대기시킨다. 대기 중인 다리와
  반대쪽이고 간격(앞 다리 끝 → 이 다리 시작)이 `max_pair_gap_ms` 이하이면 둘을 묶는다.
  **같은 쪽 다리가 연달아 오거나 간격이 길면 대기 중이던 다리는 기록 없이 버리고**
  새 다리를 대기시킨다.
  세션이 끝날 때 짝이 없는 다리도 버린다. 버린 다리는 인정량을 늘리지 않으므로 많이 세는 쪽으로는
  틀리지 않는다.
- 다리 하나의 인정 조건: 판정 각도가 기준 이하 + 그 순간 반대 다리 엉덩이 내각이
  `min_other_hip_angle` 이상(두 다리를 함께 굽히는 스쿼트 제외, 반대 다리가 안 보이면 OUT_OF_FRAME).
  마운틴 클라이머는 렙 내내 팔 지지 각도가 `min_arm_support_angle` 이상이어야 한다(유지 각도 규칙).
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from rep_engine.config import AlternatingCfg
from rep_engine.counters.base import ExerciseCounter
from rep_engine.counters.flexion import (
    EXTENDING,
    FLEXING,
    REST,
    WAIT_REST,
    FlexionCounter,
    RepDraft,
)
from rep_engine.features.chain import AlternatingFeatures
from rep_engine.schemas import AnyRepEvent, RepReason

#: 사유 우선순위 (flexion.py와 같음)
_PRIORITY = (RepReason.OUT_OF_FRAME, RepReason.TOO_FAST, RepReason.SHALLOW_DEPTH)

LEFT = "L"
RIGHT = "R"


class LegCounter(FlexionCounter):
    """다리 하나의 판정기. 결과를 내보내지 않고 `done`에 모은다 (`AlternatingCounter`가 가져감)."""

    def __init__(self, cfg: AlternatingCfg, hold_limit: float | None) -> None:
        super().__init__(cfg)
        self._min_other = cfg.min_other_hip_angle
        self._hold_limit = hold_limit
        self.done: list[RepDraft] = []

    @property
    def _hold_accept_angle(self) -> float | None:
        return self._hold_limit

    def _bottom_form_reason(self, form_at_bottom: float | None) -> RepReason | None:
        # form_at_bottom = 이 다리를 가장 높이 올린 순간 반대 다리의 엉덩이 내각
        if form_at_bottom is None:
            return RepReason.OUT_OF_FRAME
        if form_at_bottom < self._min_other:
            return RepReason.SHALLOW_DEPTH
        return None

    def _emit(self, d: RepDraft) -> list[AnyRepEvent]:
        self.done.append(d)
        return []

    def _event(self, d: RepDraft) -> AnyRepEvent:  # pragma: no cover  (_emit이 대신함)
        raise NotImplementedError("다리 판정 결과는 AlternatingCounter가 묶어서 내보낸다")


@dataclass(frozen=True, slots=True)
class PairDraft:
    """두 다리를 묶은 렙의 종목 공통 값. 하위 클래스가 종목별 렙 결과를 만든다."""

    index: int
    start_t: int
    bottom_t: int
    end_t: int
    reason: RepReason | None
    left: RepDraft
    right: RepDraft
    #: 각 다리를 올린 순간 반대 다리 엉덩이 내각 중 작은 값 (못 쟀으면 None)
    min_other_hip: float | None
    #: 두 다리 렙 동안 유지 각도(팔 지지)의 최저값 (규칙이 없거나 못 쟀으면 None)
    min_hold: float | None
    invalid_ratio: float


def _min_opt(*vals: float | None) -> float | None:
    present = [v for v in vals if v is not None]
    return min(present) if present else None


class AlternatingCounter(ExerciseCounter[AlternatingFeatures]):
    """두 다리를 묶어 1렙으로 세는 판정기의 공통 부분."""

    def __init__(self, cfg: AlternatingCfg, hold_limit: float | None = None) -> None:
        self._left = LegCounter(cfg, hold_limit)
        self._right = LegCounter(cfg, hold_limit)
        self._max_gap = cfg.max_pair_gap_ms
        self._pending: tuple[str, RepDraft] | None = None
        self._index = 0
        self._accepted = 0

    @abstractmethod
    def _event(self, p: PairDraft) -> AnyRepEvent:
        """종목별 렙 결과 (반올림 포함)."""

    @property
    def state(self) -> str:
        states = {self._left.state, self._right.state}
        for s in (FLEXING, EXTENDING, WAIT_REST):
            if s in states:
                return s
        return REST

    @property
    def current_angle(self) -> float | None:
        return _min_opt(self._left.current_angle, self._right.current_angle)

    @property
    def accepted_count(self) -> int:
        return self._accepted

    def _pair(self, left: RepDraft, right: RepDraft) -> AnyRepEvent:
        reasons = {left.reason, right.reason}
        reason = next((r for r in _PRIORITY if r in reasons), None)
        self._index += 1
        if reason is None:
            self._accepted += 1
        deeper = left if left.min_angle <= right.min_angle else right
        return self._event(
            PairDraft(
                index=self._index,
                start_t=min(left.start_t, right.start_t),
                bottom_t=deeper.bottom_t,
                end_t=max(left.end_t, right.end_t),
                reason=reason,
                left=left,
                right=right,
                min_other_hip=_min_opt(left.form_at_bottom, right.form_at_bottom),
                min_hold=_min_opt(left.min_hold, right.min_hold),
                invalid_ratio=max(left.invalid_ratio, right.invalid_ratio),
            )
        )

    def update(self, features: AlternatingFeatures) -> list[AnyRepEvent]:
        """프레임 1개 처리. 이번 프레임에서 짝이 지어진 렙(0~1개)을 돌려준다."""
        self._left.update(features.left)
        self._right.update(features.right)
        legs = [(LEFT, d) for d in self._left.done] + [(RIGHT, d) for d in self._right.done]
        self._left.done.clear()
        self._right.done.clear()
        legs.sort(key=lambda x: (x[1].end_t, x[0]))
        out: list[AnyRepEvent] = []
        for side, d in legs:
            pending = self._pending
            if (
                pending is None
                or pending[0] == side
                or d.start_t - pending[1].end_t > self._max_gap
            ):
                self._pending = (side, d)  # 짝이 없던 앞 다리는 버림 (모듈 설명)
                continue
            self._pending = None
            left, right = (pending[1], d) if pending[0] == LEFT else (d, pending[1])
            out.append(self._pair(left, right))
        return out
