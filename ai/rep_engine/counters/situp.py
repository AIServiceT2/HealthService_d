"""윗몸 일으키기 렙 판정기 (규칙은 `flexion.py`).

판정 각도 = 상체 각도(어깨–엉덩이–발목), 둘째 판정 각도 = 엉덩이 각도(어깨–엉덩이–무릎).
둘 다 기준을 넘어야 인정한다 (D-70).
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, SitupCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, SitupRepEvent


class SitupCounter(FlexionCounter):
    """윗몸 일으키기 판정기."""

    def __init__(self, cfg: SitupCfg) -> None:
        super().__init__(cfg)
        self._hip_accept = cfg.hip_accept_angle

    @property
    def _aux_accept_angle(self) -> float | None:
        return self._hip_accept

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> SitupCounter:
        if cfg.situp is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 situp 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "SITUP"},
            )
        return cls(cfg.situp)

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return SitupRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_torso_angle=r_angle(d.min_angle),
            min_hip_angle=r_opt_angle(d.min_aux),
            knee_angle_at_bottom=r_opt_angle(d.form_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("SITUP", SitupCounter.from_config)
