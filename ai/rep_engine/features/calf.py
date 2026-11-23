"""카프 레이즈의 프레임 특징 (D-92).

공통 골격(13개 관절)에는 발뒤꿈치·발끝이 없다(MoveNet). 그래서 **발목이 바닥 위치에서 얼마나
올라갔는지**로 본다.

- 발목 위치 = 보이는 발목들의 화면 y 평균 (y는 아래로 증가).
- 바닥 위치 = 최근 `floor_window_ms` 동안의 발목 위치 중 가장 낮은 곳(y가 가장 큰 값).
- 발목 높이(%) = (바닥 위치 − 지금 위치) ÷ 다리 길이(보이는 엉덩이–발목 거리 평균) × 100.
- 판정 값 = 100 − 발목 높이(%). 서 있으면 100, 발뒤꿈치를 들수록 작아진다. 다른 종목의 판정 각도와
  같은 방향이라 같은 상태 머신(`FlexionCounter`)을 쓴다. **각도가 아니다.**

보조 값(`form_angle`) = 발목 높이(%) 그대로(점프 판정용),
유지 값(`hold_angle`) = 무릎 내각(보이는 쪽 평균).
판정 값에만 One Euro 필터를 쓴다. 발목이 하나도 안 보이거나 다리 길이를 못 재면 무효 프레임.

**한계:** 사람이 카메라 쪽으로 다가가거나 폰이 흔들리면 화면 y가 바뀌어 바닥 위치가 틀어진다
(D-79와 같음). 세션을 발뒤꿈치를 든 채 시작하면 그 위치를 바닥으로 본다.
"""

from __future__ import annotations

from collections import deque

from rep_engine.adapters import SkeletonFrame
from rep_engine.config import FeaturesCfg, TorsoRangeCfg
from rep_engine.features.chain import (
    ChainFeatures,
    Joints,
    _torso_leg_ratio,
    _vis,
    floor_and_leg,
    knee_angle,
)
from rep_engine.features.filters import OneEuroFilter
from rep_engine.features.posture import posture_ok
from rep_engine.landmarks import Joint

#: 판정 값 = PERCENT − 발목 높이(%). 비율을 백분율로 바꾸는 정의상 상수
PERCENT = 100.0
_ANKLES = (Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE)


def ankle_y(joints: Joints, min_vis: float) -> tuple[float, float] | None:
    """(보이는 발목 y 평균, 그 발목들의 가시도 평균). 하나도 안 보이면 None."""
    pts = [p for j in _ANKLES if (p := _vis(joints[j], min_vis)) is not None]
    if not pts:
        return None
    return sum(p.y for p in pts) / len(pts), sum(p.vis for p in pts) / len(pts)


def calf_quality(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
    """확신도용 프레임 품질: 발목과 다리 길이를 잴 수 있으면 유효."""
    if frame.joints is None:
        return False, None
    a = ankle_y(frame.joints, min_visibility)
    _, leg = floor_and_leg(frame.joints, min_visibility)
    if a is None or not leg:
        return False, None
    return True, a[1]


class CalfFeatureExtractor:
    """스트리밍 특징 추출기. 바닥 위치를 기억하므로 프레임을 시각 순서대로 넣는다."""

    def __init__(
        self, cfg: FeaturesCfg, floor_window_ms: int, posture: TorsoRangeCfg | None = None
    ) -> None:
        self._cfg = cfg
        self._window = floor_window_ms
        self._posture = posture
        self._floor: deque[tuple[int, float]] = deque()  # (t, 발목 y)
        self._filter = OneEuroFilter(
            cfg.one_euro.min_cutoff, cfg.one_euro.beta, cfg.one_euro.d_cutoff
        )
        self._last_valid_t: int | None = None

    def update(self, frame: SkeletonFrame) -> ChainFeatures:
        joints = frame.joints
        mv = self._cfg.min_visibility
        if joints is None or not posture_ok(joints, mv, self._posture):
            return ChainFeatures(frame.t, False)
        a = ankle_y(joints, mv)
        _, leg = floor_and_leg(joints, mv)
        if a is None or not leg:
            return ChainFeatures(frame.t, False)
        y, vis = a
        while self._floor and frame.t - self._floor[0][0] > self._window:
            self._floor.popleft()
        self._floor.append((frame.t, y))
        floor = max(v for _, v in self._floor)
        lift_pct = (floor - y) / leg * PERCENT
        raw = PERCENT - lift_pct
        if (
            self._last_valid_t is not None
            and frame.t - self._last_valid_t >= self._cfg.filter_reset_gap_ms
        ):
            self._filter.reset()
        self._last_valid_t = frame.t
        return ChainFeatures(
            t=frame.t,
            valid=True,
            angle=self._filter(raw, frame.t),
            angle_raw=raw,
            form_angle=lift_pct,
            hold_angle=knee_angle(joints, mv),
            core_visibility=vis,
            torso_leg_ratio=_torso_leg_ratio(joints, mv),
        )
