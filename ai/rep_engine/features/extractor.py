"""공통 골격 프레임 → 프레임 특징 (SPEC 4장).

특징 정의 (모든 각도는 도, 거리는 픽셀):
- `knee_angle`: 엉덩이–무릎–발목 **내각**. 펴면 약 180°, 앉으면 작아짐. One Euro 필터 적용 값.
  판정 상태 머신은 이 값을 쓴다. (`kneeFlexion` = 180 − kneeAngle 은 요약에서 계산)
- `trunk_lean`: 어깨 중점→엉덩이 중점 벡터와 수직선 사이 각도. 0° = 꼿꼿이 섬.
- `hip_drop`: (엉덩이 높이 − 기준 엉덩이 높이) ÷ 기준 다리 길이(엉덩이–발목).
  기준 자세 보정 전에는 None.
- `knee_asymmetry`: |왼쪽 kneeAngle − 오른쪽 kneeAngle| (필터 전 값). 양쪽이 모두 보일 때만.

측면 선택: 다리별로 엉덩이·무릎·발목이 모두 `min_visibility` 이상이면 그 다리를 쓴다.
두 다리 → 평균, 한 다리 → 그쪽만, 없음 → **무효 프레임**. 사람 미검출(joints=None)도 무효.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from rep_engine.adapters import Point, SkeletonFrame
from rep_engine.config import FeaturesCfg
from rep_engine.features.filters import OneEuroFilter
from rep_engine.features.geometry import Vec, angle_deg, distance, midpoint, tilt_from_vertical_deg
from rep_engine.landmarks import LEFT_LEG, RIGHT_LEG, Joint


@dataclass(frozen=True, slots=True)
class FrameFeatures:
    """프레임 1개의 특징. `valid=False`면 각도 필드는 모두 None."""

    t: int
    valid: bool
    knee_angle: float | None = None
    knee_angle_raw: float | None = None
    trunk_lean: float | None = None
    hip_drop: float | None = None
    knee_asymmetry: float | None = None
    core_visibility: float | None = None
    #: 상체 길이 ÷ (허벅지+정강이 길이). 사람 교체 탐지(BODY_PROPORTION_SHIFT)용
    torso_leg_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class Baseline:
    """서 있는 기준 자세 (픽셀). 엉덩이 높이(y)와 다리 길이(엉덩이–발목)의 중앙값."""

    hip_y: float
    leg_length: float


@dataclass(frozen=True, slots=True)
class _Leg:
    angle: float
    hip: Point
    knee: Point
    ankle: Point


def _xy(p: Point) -> Vec:
    return (p.x, p.y)


#: 다리별 (엉덩이, 무릎, 발목) 정수 인덱스. IntEnum 인덱싱은 느려서 미리 int로 바꿔 둔다.
_LEG_INDICES: tuple[tuple[int, int, int], ...] = tuple(
    (int(h), int(k), int(a)) for h, k, a in (LEFT_LEG, RIGHT_LEG)
)


def visible_legs(joints: tuple[Point | None, ...], min_visibility: float) -> list[_Leg]:
    """측면 선택: 엉덩이·무릎·발목이 모두 `min_visibility` 이상인 다리 (왼쪽, 오른쪽 순)."""
    out: list[_Leg] = []
    for hi, ki, ai in _LEG_INDICES:
        hip, knee, ankle = joints[hi], joints[ki], joints[ai]
        if hip is None or knee is None or ankle is None:
            continue
        if hip.vis < min_visibility or knee.vis < min_visibility or ankle.vis < min_visibility:
            continue
        ang = angle_deg((hip.x, hip.y), (knee.x, knee.y), (ankle.x, ankle.y))
        if ang is not None:
            out.append(_Leg(ang, hip, knee, ankle))
    return out


def frame_quality(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
    """(유효 프레임 여부, 쓰인 핵심 관절 평균 가시도). 상태가 없어 어디서 불러도 같다."""
    if frame.joints is None:
        return False, None
    legs = visible_legs(frame.joints, min_visibility)
    if not legs:
        return False, None
    n = 3 * len(legs)
    return True, sum(p.vis for leg in legs for p in (leg.hip, leg.knee, leg.ankle)) / n


class FeatureExtractor:
    """스트리밍 특징 추출기. 프레임을 시각 순서대로 `update`에 넣는다."""

    def __init__(self, cfg: FeaturesCfg, stand_angle: float) -> None:
        self._cfg = cfg
        self._stand_angle = stand_angle
        self._filter = OneEuroFilter(
            cfg.one_euro.min_cutoff, cfg.one_euro.beta, cfg.one_euro.d_cutoff
        )
        self._last_valid_t: int | None = None
        self.baseline: Baseline | None = None
        self._calib: list[tuple[int, float, float]] = []

    def _visible(self, p: Point | None) -> Point | None:
        return p if p is not None and p.vis >= self._cfg.min_visibility else None

    def update(self, frame: SkeletonFrame) -> FrameFeatures:
        """프레임 1개를 처리한다."""
        joints = frame.joints
        legs = [] if joints is None else visible_legs(joints, self._cfg.min_visibility)
        if joints is None or not legs:
            # 무효 프레임: 기준 자세 연속 구간도 끊는다
            if self.baseline is None:
                self._calib.clear()
            return FrameFeatures(frame.t, False)

        # 무효 구간이 길었으면 필터 초기화
        if (
            self._last_valid_t is not None
            and frame.t - self._last_valid_t >= self._cfg.filter_reset_gap_ms
        ):
            self._filter.reset()
        self._last_valid_t = frame.t

        raw = sum(leg.angle for leg in legs) / len(legs)
        knee_angle = self._filter(raw, frame.t)
        asym = abs(legs[0].angle - legs[1].angle) if len(legs) == 2 else None
        core_vis = sum(p.vis for leg in legs for p in (leg.hip, leg.knee, leg.ankle)) / (
            3 * len(legs)
        )
        hip_y = sum(leg.hip.y for leg in legs) / len(legs)
        leg_len = sum(distance(_xy(leg.hip), _xy(leg.ankle)) for leg in legs) / len(legs)
        limb_len = sum(
            distance(_xy(leg.hip), _xy(leg.knee)) + distance(_xy(leg.knee), _xy(leg.ankle))
            for leg in legs
        ) / len(legs)
        hip_mid = midpoint(_xy(legs[0].hip), _xy(legs[-1].hip))

        shoulders = [
            s
            for s in (
                self._visible(joints[Joint.LEFT_SHOULDER]),
                self._visible(joints[Joint.RIGHT_SHOULDER]),
            )
            if s is not None
        ]
        trunk_lean: float | None = None
        ratio: float | None = None
        if shoulders:
            sh_mid = midpoint(_xy(shoulders[0]), _xy(shoulders[-1]))
            trunk_lean = tilt_from_vertical_deg(sh_mid, hip_mid)
            if limb_len > 0:
                ratio = distance(sh_mid, hip_mid) / limb_len

        self._calibrate(frame.t, knee_angle, hip_y, leg_len)
        hip_drop: float | None = None
        if self.baseline is not None and self.baseline.leg_length > 0:
            hip_drop = (hip_y - self.baseline.hip_y) / self.baseline.leg_length

        return FrameFeatures(
            t=frame.t,
            valid=True,
            knee_angle=knee_angle,
            knee_angle_raw=raw,
            trunk_lean=trunk_lean,
            hip_drop=hip_drop,
            knee_asymmetry=asym,
            core_visibility=core_vis,
            torso_leg_ratio=ratio,
        )

    def _calibrate(self, t: int, knee_angle: float, hip_y: float, leg_len: float) -> None:
        """서 있는 구간이 `calibration_window_ms` 이상 이어지면 기준 자세를 한 번 잡는다."""
        if self.baseline is not None:
            return
        if knee_angle < self._stand_angle:
            self._calib.clear()
            return
        self._calib.append((t, hip_y, leg_len))
        if t - self._calib[0][0] >= self._cfg.calibration_window_ms:
            self.baseline = Baseline(
                hip_y=median(c[1] for c in self._calib),
                leg_length=median(c[2] for c in self._calib),
            )
            self._calib.clear()
