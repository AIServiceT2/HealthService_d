"""마운틴 클라이머 렙 판정기 (D-84). 규칙은 `alternating.py`.

플랭크 자세에서 무릎을 번갈아 가슴 쪽으로 당긴다. 다리별 판정 각도 = 엉덩이 내각(어깨–엉덩이–무릎).
왼다리 1번 + 오른다리 1번 = 1렙. 렙 내내 손으로 바닥을 짚고 있어야 한다
(팔 지지 각도, 유지 각도 규칙):
누워서 무릎을 가슴으로 당기는 동작은 팔이 수평이라 인정하지 않는다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, MountainClimberCfg
from rep_engine.counters.alternating import AlternatingCounter, PairDraft
from rep_engine.counters.base import register_counter
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, MountainClimberRepEvent


class MountainClimberCounter(AlternatingCounter):
    """마운틴 클라이머 판정기."""

    def __init__(self, cfg: MountainClimberCfg) -> None:
        super().__init__(cfg, cfg.min_arm_support_angle)

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> MountainClimberCounter:
        if cfg.mountain_climber is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 mountain_climber 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "MOUNTAIN_CLIMBER"},
            )
        return cls(cfg.mountain_climber)

    def _event(self, p: PairDraft) -> AnyRepEvent:
        return MountainClimberRepEvent(
            index=p.index,
            start_t=p.start_t,
            bottom_t=p.bottom_t,
            end_t=p.end_t,
            accepted=p.reason is None,
            reason=p.reason,
            left_min_tuck_angle=r_angle(p.left.min_angle),
            right_min_tuck_angle=r_angle(p.right.min_angle),
            left_reason=p.left.reason,
            right_reason=p.right.reason,
            min_back_leg_hip_angle=r_opt_angle(p.min_other_hip),
            min_arm_support_angle=r_opt_angle(p.min_hold),
            invalid_ratio=r_ratio(p.invalid_ratio),
        )


register_counter("MOUNTAIN_CLIMBER", MountainClimberCounter.from_config)
