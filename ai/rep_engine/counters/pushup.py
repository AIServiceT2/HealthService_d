"""푸시업 렙 판정기. 판정 각도 = 팔꿈치 내각(어깨–팔꿈치–손목). 규칙은 `flexion.py`.

카탈로그에 `min_knee_angle`이 있으면 렙 내내 무릎 내각이 그 이상이어야 인정한다 (D-78).
무릎을 바닥에 대고 하면 무릎이 굽어 SHALLOW_DEPTH, 다리가 한 번도 안 보이면 OUT_OF_FRAME.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, PushupCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, PushupRepEvent


class PushupCounter(FlexionCounter):
    """푸시업 판정기."""

    def __init__(self, cfg: PushupCfg) -> None:
        super().__init__(cfg)
        self._min_knee = cfg.min_knee_angle

    @property
    def _hold_accept_angle(self) -> float | None:
        """무릎이 렙 내내 펴져 있어야 인정 (무릎 대고 하는 푸시업 제외, D-78)."""
        return self._min_knee

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> PushupCounter:
        if cfg.pushup is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 pushup 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "PUSHUP"},
            )
        return cls(cfg.pushup)

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return PushupRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_elbow_angle=r_angle(d.min_angle),
            body_line_dev_at_bottom=r_opt_angle(d.form_at_bottom),
            elbow_asymmetry_at_bottom=r_opt_angle(d.asymmetry_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
            min_knee_angle_in_rep=r_opt_angle(d.min_hold),
        )


register_counter("PUSHUP", PushupCounter.from_config)
