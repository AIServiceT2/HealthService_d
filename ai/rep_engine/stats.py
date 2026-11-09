"""작은 통계 함수 (모집단 표준편차). 모바일 포팅이 쉽도록 표준 라이브러리만 쓴다."""

from __future__ import annotations

import math
from collections.abc import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def pstdev(xs: Sequence[float]) -> float:
    """모집단 표준편차 (n으로 나눔). 값이 1개면 0."""
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0
