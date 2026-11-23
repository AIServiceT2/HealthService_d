"""리버스 크런치 렙 판정기 (D-89). 규칙은 `flexion.py`.

누워서 무릎을 90°로 든 자세에서 무릎을 가슴 쪽으로 말아 올렸다 내리면 1렙. 판정 각도 = 엉덩이 내각
(어깨–엉덩이–무릎, 보이는 쪽 평균).

렙 내내 상체 방향(엉덩이→어깨 선이 화면 위쪽에서 기운 각도)이 `min_torso_tilt` 이상이어야 인정한다
(유지 각도 규칙). 어깨가 바닥에 붙어 있는지 보는 것이다. 윗몸 일으키기도 엉덩이 내각이 작아지는데,
상체를 일으키므로 이 조건으로 거른다. 상체를 못 재면 OUT_OF_FRAME.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, ReverseCrunchCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, ReverseCrunchRepEvent


class ReverseCrunchCounter(FlexionCounter):
    """리버스 크런치 판정기."""

    def __init__(self, cfg: ReverseCrunchCfg) -> None:
        super().__init__(cfg)
        self._hold_limit = cfg.min_torso_tilt

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> ReverseCrunchCounter:
        if cfg.reverse_crunch is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 reverse_crunch 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "REVERSE_CRUNCH"},
            )
        return cls(cfg.reverse_crunch)

    @property
    def _hold_accept_angle(self) -> float | None:
        return self._hold_limit

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return ReverseCrunchRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_crunch_hip_angle=r_angle(d.min_angle),
            knee_angle_at_top=r_opt_angle(d.form_at_bottom),
            min_torso_tilt=r_opt_angle(d.min_hold),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("REVERSE_CRUNCH", ReverseCrunchCounter.from_config)
