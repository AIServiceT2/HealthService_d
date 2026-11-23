"""버드독 렙 판정기 (D-91). 규칙은 `alternating.py`. 측면 촬영.

네발 자세에서 **반대쪽** 팔과 다리를 함께 뻗었다 돌아오면 그 쪽 1번. 왼쪽 동작(왼팔+오른다리) 1번 +
오른쪽 동작(오른팔+왼다리) 1번 = 1렙 (요청자 결정, 2026-11-23).

쪽별 판정 값 = 180 − min(팔 뻗음, 다리 뻗음). 팔 뻗음 = 엉덩이–어깨–손목 내각, 다리 뻗음 =
어깨–엉덩이–무릎 내각. 팔과 다리를 **둘 다** 뻗어야 작아진다. 같은 쪽 팔·다리(왼팔+왼다리)를 뻗으면
어느 쪽 판정 값도 작아지지 않아 세지 않는다.

가장 뻗은 순간 받치는(반대쪽) 팔의 팔 지지 각도가 `min_support_arm_angle` 이상이어야 인정한다.
엎드려 양팔·다리를 드는 슈퍼맨은 받치는 팔이 없어 거른다.
"""

from __future__ import annotations

from rep_engine.config import BirdDogCfg, EngineConfig
from rep_engine.counters.alternating import AlternatingCounter, PairDraft
from rep_engine.counters.base import register_counter
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import FULL_EXTENSION_DEG
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, BirdDogRepEvent


class BirdDogCounter(AlternatingCounter):
    """버드독 판정기."""

    def __init__(self, cfg: BirdDogCfg) -> None:
        super().__init__(cfg, cfg.min_support_arm_angle, cfg.max_pair_gap_ms)

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> BirdDogCounter:
        if cfg.bird_dog is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 bird_dog 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "BIRD_DOG"},
            )
        return cls(cfg.bird_dog)

    def _event(self, p: PairDraft) -> AnyRepEvent:
        return BirdDogRepEvent(
            index=p.index,
            start_t=p.start_t,
            bottom_t=p.bottom_t,
            end_t=p.end_t,
            accepted=p.reason is None,
            reason=p.reason,
            left_side_extension=r_angle(FULL_EXTENSION_DEG - p.left.min_angle),
            right_side_extension=r_angle(FULL_EXTENSION_DEG - p.right.min_angle),
            left_reason=p.left.reason,
            right_reason=p.right.reason,
            min_support_arm_angle=r_opt_angle(p.min_other),
            invalid_ratio=r_ratio(p.invalid_ratio),
        )


register_counter("BIRD_DOG", BirdDogCounter.from_config)
