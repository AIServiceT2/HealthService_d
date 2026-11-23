"""사이드 런지 렙 판정기 (D-90). 규칙은 `alternating.py`. **정면 촬영.**

한쪽 다리를 옆으로 굽혔다 펴면 그 쪽 1번, 왼쪽 1번 + 오른쪽 1번 = 1렙 (요청자 결정, 2026-11-23).
쪽별 판정 각도 = 굽힌 다리의 무릎 내각(엉덩이–무릎–발목, 화면에 보이는 2D 각도).

쪽별 인정 조건:
- 무릎 내각이 기준 이하.
- 가장 굽힌 순간 반대 다리 무릎 내각이 `min_other_knee_angle` 이상
  (편 다리, 두 무릎을 굽히는 스쿼트 제외).
- 렙 동안 다리 벌림 최댓값이 `min_leg_spread_deg` 이상(옆으로 벌리지 않고 무릎만 굽히는 동작 제외).
  둘째 판정 각도(180 − 벌림)로 넣어 공통 규칙을 그대로 쓴다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, SideLungeCfg
from rep_engine.counters.alternating import AlternatingCounter, PairDraft
from rep_engine.counters.base import register_counter
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import FULL_EXTENSION_DEG
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, SideLungeRepEvent


class SideLungeCounter(AlternatingCounter):
    """사이드 런지 판정기."""

    def __init__(self, cfg: SideLungeCfg) -> None:
        super().__init__(
            cfg,
            cfg.min_other_knee_angle,
            cfg.max_pair_gap_ms,
            aux_limit=FULL_EXTENSION_DEG - cfg.min_leg_spread_deg,
        )

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> SideLungeCounter:
        if cfg.side_lunge is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 side_lunge 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "SIDE_LUNGE"},
            )
        return cls(cfg.side_lunge)

    def _event(self, p: PairDraft) -> AnyRepEvent:
        spread = None if p.max_min_aux is None else FULL_EXTENSION_DEG - p.max_min_aux
        return SideLungeRepEvent(
            index=p.index,
            start_t=p.start_t,
            bottom_t=p.bottom_t,
            end_t=p.end_t,
            accepted=p.reason is None,
            reason=p.reason,
            left_min_knee_angle=r_angle(p.left.min_angle),
            right_min_knee_angle=r_angle(p.right.min_angle),
            left_reason=p.left.reason,
            right_reason=p.right.reason,
            min_other_knee_angle=r_opt_angle(p.min_other),
            min_lateral_spread=r_opt_angle(spread),
            invalid_ratio=r_ratio(p.invalid_ratio),
        )


register_counter("SIDE_LUNGE", SideLungeCounter.from_config)
