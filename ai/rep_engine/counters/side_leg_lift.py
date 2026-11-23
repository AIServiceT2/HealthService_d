"""사이드 레그 리프트 렙 판정기 (규칙은 `flexion.py`, D-77).

판정 각도 = 180 − 다리 벌림(왼·오른 엉덩이→발목 선 사이 각도). 특징 단계
(`SIDE_LEG_LIFT_SPEC`, `pair=True`, `invert=True`)에서 바꿔 두므로 상태 머신은 다른 종목과 같다:
다리를 모은 자세(약 180°)에서 위쪽 다리를 들수록 작아지고, `depth_accept_angle` 이하
(충분히 벌림)까지 들어야 인정한다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, SideLegLiftCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import FULL_EXTENSION_DEG
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, SideLegLiftRepEvent


class SideLegLiftCounter(FlexionCounter):
    """사이드 레그 리프트 판정기."""

    def __init__(self, cfg: SideLegLiftCfg) -> None:
        super().__init__(cfg)

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> SideLegLiftCounter:
        if cfg.side_leg_lift is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 side_leg_lift 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "SIDE_LEG_LIFT"},
            )
        return cls(cfg.side_leg_lift)

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return SideLegLiftRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            max_leg_spread=r_angle(FULL_EXTENSION_DEG - d.min_angle),
            knee_angle_at_top=r_opt_angle(d.form_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("SIDE_LEG_LIFT", SideLegLiftCounter.from_config)
