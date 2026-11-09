"""출력 반올림 규칙 (SPEC 13장: 각도 소수 1자리, 확신도 소수 3자리).

모바일 구현과 같은 결과를 내도록 **0.5는 올림(half-up)**으로 통일한다.
Python 기본 `round`(짝수 반올림)는 쓰지 않는다.
"""

from __future__ import annotations

import math

ANGLE_DECIMALS = 1
RATIO_DECIMALS = 3
CONFIDENCE_DECIMALS = 3
MS_DECIMALS = 1


def round_half_up(value: float, decimals: int) -> float:
    """소수 `decimals`자리에서 0.5를 올림한다."""
    factor = 10.0**decimals
    return math.floor(value * factor + 0.5) / factor


def r_angle(value: float) -> float:
    return round_half_up(value, ANGLE_DECIMALS)


def r_ratio(value: float) -> float:
    return round_half_up(value, RATIO_DECIMALS)


def r_opt_angle(value: float | None) -> float | None:
    return None if value is None else r_angle(value)


def r_opt_ratio(value: float | None) -> float | None:
    return None if value is None else r_ratio(value)


def r_ms(value: float) -> float:
    return round_half_up(value, MS_DECIMALS)
