"""One Euro 필터 (Casiez et al., 2012). 외부 라이브러리 없이 직접 구현한 결정적 버전.

시간은 프레임의 `t`(ms) 차이만 쓴다. 벽시계를 쓰지 않는다.
"""

from __future__ import annotations

import math

_MS_PER_S = 1000.0


def _alpha(cutoff_hz: float, dt_s: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / dt_s)


class OneEuroFilter:
    """스칼라 One Euro 필터.

    Args:
        min_cutoff: 최소 차단 주파수(Hz). 작을수록 정지 상태 떨림을 더 줄인다.
        beta: 속도 계수. 클수록 빠른 움직임의 지연이 줄어든다.
        d_cutoff: 미분값 필터의 차단 주파수(Hz).
    """

    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: float | None = None
        self._dx = 0.0
        self._t_ms: int | None = None

    def reset(self) -> None:
        """필터 상태 초기화 (다음 값은 그대로 통과)."""
        self._x = None
        self._dx = 0.0
        self._t_ms = None

    def __call__(self, value: float, t_ms: int) -> float:
        """값 하나를 거른다. `t_ms`가 이전과 같거나 작으면 이전 출력을 그대로 돌려준다."""
        if self._x is None or self._t_ms is None:
            self._x = value
            self._dx = 0.0
            self._t_ms = t_ms
            return value
        if t_ms <= self._t_ms:
            return self._x
        dt_s = (t_ms - self._t_ms) / _MS_PER_S
        dx = (value - self._x) / dt_s
        a_d = _alpha(self.d_cutoff, dt_s)
        self._dx = a_d * dx + (1.0 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = _alpha(cutoff, dt_s)
        self._x = a * value + (1.0 - a) * self._x
        self._t_ms = t_ms
        return self._x
