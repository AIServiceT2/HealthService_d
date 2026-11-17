"""종목별 자세(서기·엎드리기·눕기) 확인 (D-75).

상체 방향 = 엉덩이 중점→어깨 중점 선이 화면 위쪽에서 기운 각도(도, 0~180).
0° = 똑바로 섬, 90° = 수평(누움·엎드림), 180° = 거꾸로(어깨가 엉덩이보다 아래).
화면의 위쪽을 중력 방향의 반대로 보므로 **폰을 세로로 세워 둔다고 가정**한다.

고른 종목과 다른 자세(예: 글루트 브릿지를 골랐는데 서 있음)의 프레임을 무효로 만들어
렙으로 세지 않게 한다. 운동 종류를 자동으로 알아내지는 않는다.
"""

from __future__ import annotations

from rep_engine.adapters import Point
from rep_engine.config import TorsoRangeCfg
from rep_engine.features.geometry import midpoint, tilt_from_vertical_deg
from rep_engine.landmarks import Joint

Joints = tuple[Point | None, ...]

_SHOULDERS = (int(Joint.LEFT_SHOULDER), int(Joint.RIGHT_SHOULDER))
_HIPS = (int(Joint.LEFT_HIP), int(Joint.RIGHT_HIP))


def _visible_mid(
    joints: Joints, idx: tuple[int, int], min_vis: float
) -> tuple[float, float] | None:
    pts = [p for i in idx if (p := joints[i]) is not None and p.vis >= min_vis]
    if not pts:
        return None
    return midpoint((pts[0].x, pts[0].y), (pts[-1].x, pts[-1].y))


def torso_from_up(joints: Joints, min_vis: float) -> float | None:
    """상체 방향(도). 어깨나 엉덩이가 하나도 안 보이면 None."""
    sh = _visible_mid(joints, _SHOULDERS, min_vis)
    hip = _visible_mid(joints, _HIPS, min_vis)
    if sh is None or hip is None:
        return None
    return tilt_from_vertical_deg(sh, hip)


def posture_ok(joints: Joints, min_vis: float, rng: TorsoRangeCfg | None) -> bool:
    """자세 확인을 통과했는가. 확인하지 않는 종목(rng=None)이면 항상 True.

    상체 방향을 잴 수 없으면(어깨·엉덩이가 안 보임) 통과하지 않는다 — 가려서 확인을 피할 수 없게.
    """
    if rng is None:
        return True
    angle = torso_from_up(joints, min_vis)
    return angle is not None and rng.min_deg <= angle <= rng.max_deg
