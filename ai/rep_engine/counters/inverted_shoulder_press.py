"""인버티드 숄더 프레스(파이크 자세) 렙 판정기 (규칙은 `flexion.py`, D-72).

판정 각도 = 팔꿈치 내각(어깨–팔꿈치–손목). 둘째 판정 각도 = 엉덩이 각도(어깨–엉덩이–발목).
렙 동안 엉덩이 각도 최저값이 `pike_hip_accept_angle` 이하여야 인정한다(엉덩이를 높이 접은 파이크
자세). 일반 푸시업(엉덩이 약 180°)은 이 조건에서 SHALLOW_DEPTH로 미인정된다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, InvertedShoulderPressCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, InvertedShoulderPressRepEvent


class InvertedShoulderPressCounter(FlexionCounter):
    """인버티드 숄더 프레스 판정기."""

    def __init__(self, cfg: InvertedShoulderPressCfg) -> None:
        super().__init__(cfg)
        self._pike_accept = cfg.pike_hip_accept_angle

    @property
    def _aux_accept_angle(self) -> float | None:
        return self._pike_accept

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> InvertedShoulderPressCounter:
        if cfg.inverted_shoulder_press is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 inverted_shoulder_press 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "INVERTED_SHOULDER_PRESS"},
            )
        return cls(cfg.inverted_shoulder_press)

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return InvertedShoulderPressRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_elbow_angle=r_angle(d.min_angle),
            min_pike_hip_angle=r_opt_angle(d.min_aux),
            knee_angle_at_bottom=r_opt_angle(d.form_at_bottom),
            elbow_asymmetry_at_bottom=r_opt_angle(d.asymmetry_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("INVERTED_SHOULDER_PRESS", InvertedShoulderPressCounter.from_config)
