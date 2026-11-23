"""런지 렙 판정기 (규칙은 `flexion.py`, D-71).

판정 각도 = 무릎 내각(엉덩이–무릎–발목, 보이는 다리 평균). 런지는 앞·뒷다리 무릎이 함께 굽어서
평균을 써도 된다고 가정했다.
스쿼트도 무릎 각도만 보면 런지로 세어지므로, 최저점의 좌우 엉덩이 각도 차가 `min_hip_spread_deg`
이상이어야 인정한다. 양쪽 엉덩이 각도를 다 재지 못하면 OUT_OF_FRAME, 기준 미달이면
SHALLOW_DEPTH(새 사유를 만들지 않음, 렙 결과의 `hipSpreadAtBottom`으로 구별)다.

점프 판정 (D-79): 공통 '발 뜸' 규칙(`flexion.py`, 카탈로그 `lunge.feet_down`)을 쓴다. 렙 시작
`airborne_lookback_ms` 전부터 렙 끝까지 바닥 쪽 발이 한 번이라도 떴으면 SHALLOW_DEPTH (렙 결과
`maxFootLift`로 구별). 점프는 렙이 끝난(무릎을 편) 직후에 뜨므로, 착지한 다음 렙에서 잡힌다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, LungeCfg
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.rounding import r_angle, r_opt_angle, r_opt_ratio, r_ratio
from rep_engine.schemas import AnyRepEvent, LungeRepEvent, RepReason


class LungeCounter(FlexionCounter):
    """런지 판정기."""

    def __init__(self, cfg: LungeCfg) -> None:
        super().__init__(cfg, cfg.feet_down)
        self._min_spread = cfg.min_hip_spread_deg

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> LungeCounter:
        if cfg.lunge is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 lunge 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "LUNGE"},
            )
        return cls(cfg.lunge)

    def _bottom_form_reason(self, form_at_bottom: float | None) -> RepReason | None:
        if form_at_bottom is None:
            return RepReason.OUT_OF_FRAME
        if form_at_bottom < self._min_spread:
            return RepReason.SHALLOW_DEPTH
        return None

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return LungeRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            min_knee_angle=r_angle(d.min_angle),
            hip_spread_at_bottom=r_opt_angle(d.form_at_bottom),
            knee_asymmetry_at_bottom=r_opt_angle(d.asymmetry_at_bottom),
            invalid_ratio=r_ratio(d.invalid_ratio),
            max_foot_lift=r_opt_ratio(d.max_foot_lift),
        )


register_counter("LUNGE", LungeCounter.from_config)
