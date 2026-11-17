"""글루트 브릿지 렙 판정기 (규칙은 `flexion.py`, D-73).

판정 각도 = 엉덩이 굽힘 = 180 − 엉덩이 내각(어깨–엉덩이–무릎). 특징 단계(`GLUTE_BRIDGE_SPEC`,
`invert=True`)에서 바꿔 두므로 상태 머신은 다른 종목과 같다: 누운 자세(약 45°)에서 엉덩이를 들수록
작아지고, `depth_accept_angle` 이하(어깨–엉덩이–무릎이 거의 일직선)까지 들어야 인정한다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, GluteBridgeCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, GluteBridgeRepEvent


class GluteBridgeCounter(FlexionCounter):
    """글루트 브릿지 판정기."""

    def __init__(self, cfg: GluteBridgeCfg) -> None:
        super().__init__(cfg)

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> GluteBridgeCounter:
        if cfg.glute_bridge is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 glute_bridge 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "GLUTE_BRIDGE"},
            )
        return cls(cfg.glute_bridge)

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return GluteBridgeRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_hip_flexion=r_angle(d.min_angle),
            knee_angle_at_top=r_opt_angle(d.form_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("GLUTE_BRIDGE", GluteBridgeCounter.from_config)
