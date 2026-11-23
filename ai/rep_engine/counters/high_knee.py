"""하이 니 렙 판정기 (D-83). 규칙은 `alternating.py`.

선 자세에서 무릎을 번갈아 엉덩이 높이 가까이 올린다.
다리별 판정 각도 = 엉덩이 내각(어깨–엉덩이–무릎).
왼다리 1번 + 오른다리 1번 = 1렙.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, HighKneeCfg
from rep_engine.counters.alternating import AlternatingCounter, PairDraft
from rep_engine.counters.base import register_counter
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, HighKneeRepEvent


class HighKneeCounter(AlternatingCounter):
    """하이 니 판정기."""

    def __init__(self, cfg: HighKneeCfg) -> None:
        super().__init__(cfg, cfg.min_other_hip_angle, cfg.max_pair_gap_ms)

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> HighKneeCounter:
        if cfg.high_knee is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 high_knee 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "HIGH_KNEE"},
            )
        return cls(cfg.high_knee)

    def _event(self, p: PairDraft) -> AnyRepEvent:
        return HighKneeRepEvent(
            index=p.index,
            start_t=p.start_t,
            bottom_t=p.bottom_t,
            end_t=p.end_t,
            accepted=p.reason is None,
            reason=p.reason,
            left_min_hip_angle=r_angle(p.left.min_angle),
            right_min_hip_angle=r_angle(p.right.min_angle),
            left_reason=p.left.reason,
            right_reason=p.right.reason,
            min_standing_hip_angle=r_opt_angle(p.min_other),
            invalid_ratio=r_ratio(p.invalid_ratio),
        )


register_counter("HIGH_KNEE", HighKneeCounter.from_config)
