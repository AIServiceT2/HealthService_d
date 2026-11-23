"""카프 레이즈 렙 판정기 (D-92). 규칙은 `flexion.py`, 특징은 `features/calf.py`.

서서 발뒤꿈치를 들었다 내리면 1렙. 판정 값 = 100 − 발목 높이(%) (각도가 아님). 발목 높이 =
바닥 위치에서 발목이 올라간 정도 ÷ 다리 길이.

- 렙 내내 무릎 내각이 `min_knee_angle` 이상이어야 인정 (유지 각도 규칙. 무릎을 굽혀 튀는 동작 제외).
- 가장 높이 든 순간 발목 높이가 `max_lift_pct`를 넘으면 점프로 보고 SHALLOW_DEPTH
  (점프 런지 D-79와 같은 사유, 렙 결과 `maxAnkleLiftPct`로 구별).
"""

from __future__ import annotations

from rep_engine.config import CalfRaiseCfg, EngineConfig
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.calf import PERCENT
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, CalfRaiseRepEvent, RepReason


class CalfRaiseCounter(FlexionCounter):
    """카프 레이즈 판정기."""

    def __init__(self, cfg: CalfRaiseCfg) -> None:
        super().__init__(cfg)
        self._hold_limit = cfg.min_knee_angle
        self._max_lift = cfg.max_lift_pct

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> CalfRaiseCounter:
        if cfg.calf_raise is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 calf_raise 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "CALF_RAISE"},
            )
        return cls(cfg.calf_raise)

    @property
    def _hold_accept_angle(self) -> float | None:
        return self._hold_limit

    def _bottom_form_reason(self, form_at_bottom: float | None) -> RepReason | None:
        # form_at_bottom = 가장 높이 든 순간의 발목 높이(%, 필터 전)
        if form_at_bottom is not None and form_at_bottom > self._max_lift:
            return RepReason.SHALLOW_DEPTH
        return None

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return CalfRaiseRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            max_ankle_lift_pct=r_angle(PERCENT - d.min_angle),
            min_knee_angle_in_rep=r_opt_angle(d.min_hold),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("CALF_RAISE", CalfRaiseCounter.from_config)
