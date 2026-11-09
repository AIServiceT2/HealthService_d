"""각도·거리 계산. 입력은 모두 **픽셀 좌표**(정규화 좌표 × 이미지 크기, 종횡비 보정 후)다.

모바일 포팅을 위해 math 모듈과 사칙연산만 쓴다.
"""

from __future__ import annotations

import math

Vec = tuple[float, float]


def to_pixel(x_norm: float, y_norm: float, image_width: int, image_height: int) -> Vec:
    """정규화 좌표 → 픽셀 좌표 (종횡비 보정)."""
    return (x_norm * image_width, y_norm * image_height)


def distance(a: Vec, b: Vec) -> float:
    """두 점 사이 거리 (픽셀)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def midpoint(a: Vec, b: Vec) -> Vec:
    """두 점의 중점."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def angle_deg(a: Vec, b: Vec, c: Vec) -> float | None:
    """점 b에서 a–b–c가 이루는 **내각**(도, 0~180). 길이 0인 변이 있으면 None.

    kneeAngle = angle_deg(엉덩이, 무릎, 발목): 다리를 완전히 펴면 약 180°, 깊이 앉으면 작아진다.
    """
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 == 0.0 or n2 == 0.0:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


def tilt_from_vertical_deg(top: Vec, bottom: Vec) -> float | None:
    """top→bottom 벡터와 수직선(아래 방향) 사이 각도(도, 0~180). 0° = 똑바로 섬.

    trunkLean = tilt_from_vertical_deg(어깨 중점, 엉덩이 중점).
    """
    dx = bottom[0] - top[0]
    dy = bottom[1] - top[1]
    if dx == 0.0 and dy == 0.0:
        return None
    return math.degrees(math.atan2(abs(dx), dy))
