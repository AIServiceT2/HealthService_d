"""슈퍼맨 렙 판정기 (D-85). 규칙은 `flexion.py`.

엎드려 팔을 머리 위로 뻗고, 팔·가슴과 다리를 함께 들었다 내리면 1렙 (버티는 시간은 보지 않음,
요청자 결정 2026-11-23). 판정 각도 = 몸 활 각도(어깨–엉덩이–발목 내각): 엎드려 일직선이면 약 180°,
들수록 작아진다.

가장 높이 든 순간 팔 뻗음(엉덩이–어깨–손목 내각)이 `min_arm_reach_angle` 이상이어야 인정한다.
누워서 하는 글루트 브릿지도 어깨–엉덩이–발목 각도가 작아지는데,
팔을 몸 옆에 두므로 이 조건으로 거른다.
팔이 안 보이면 OUT_OF_FRAME, 기준 미달이면 SHALLOW_DEPTH (렙 결과 `armReachAtTop`으로 구별).
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, SupermanCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, RepReason, SupermanRepEvent


class SupermanCounter(FlexionCounter):
    """슈퍼맨 판정기."""

    def __init__(self, cfg: SupermanCfg) -> None:
        super().__init__(cfg)
        self._min_reach = cfg.min_arm_reach_angle

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> SupermanCounter:
        if cfg.superman is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 superman 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "SUPERMAN"},
            )
        return cls(cfg.superman)

    def _bottom_form_reason(self, form_at_bottom: float | None) -> RepReason | None:
        if form_at_bottom is None:
            return RepReason.OUT_OF_FRAME
        if form_at_bottom < self._min_reach:
            return RepReason.SHALLOW_DEPTH
        return None

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return SupermanRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_body_arch_angle=r_angle(d.min_angle),
            arm_reach_at_top=r_opt_angle(d.form_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("SUPERMAN", SupermanCounter.from_config)
