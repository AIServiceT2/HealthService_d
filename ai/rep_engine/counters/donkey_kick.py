"""돈키 킥 렙 판정기 (D-86). 규칙은 `flexion.py`.

네발 자세에서 한쪽 다리(무릎을 굽힌 채)를 뒤로 차 올렸다 내리면 1렙. 판정 각도 =
180 − 엉덩이 내각(어깨–엉덩이–무릎)이고, 특징 단계
(`DONKEY_KICK_SPEC`, `invert=True`, `pick="min"`)에서
좌우 중 **작은 쪽(= 찬 다리)**을 쓴다. 평균을 쓰면 받치는 다리 때문에 찬 각도가 반으로 줄어든다.
어느 쪽 다리로 차도 같다.

렙 내내 팔 지지 각도가 `min_arm_support_angle` 이상이어야 인정한다(유지 각도 규칙). 누워서 엉덩이를
드는 글루트 브릿지도 엉덩이 내각이 커지는데, 팔이 바닥에 수평이라 이 조건으로 거른다.
"""

from __future__ import annotations

from rep_engine.config import DonkeyKickCfg, EngineConfig
from rep_engine.counters.base import register_counter
from rep_engine.counters.flexion import FlexionCounter, RepDraft
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import FULL_EXTENSION_DEG
from rep_engine.rounding import r_angle, r_opt_angle, r_ratio
from rep_engine.schemas import AnyRepEvent, DonkeyKickRepEvent


class DonkeyKickCounter(FlexionCounter):
    """돈키 킥 판정기."""

    def __init__(self, cfg: DonkeyKickCfg) -> None:
        super().__init__(cfg)
        self._hold_limit = cfg.min_arm_support_angle

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> DonkeyKickCounter:
        if cfg.donkey_kick is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 donkey_kick 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "DONKEY_KICK"},
            )
        return cls(cfg.donkey_kick)

    @property
    def _hold_accept_angle(self) -> float | None:
        return self._hold_limit

    def _event(self, d: RepDraft) -> AnyRepEvent:
        return DonkeyKickRepEvent(
            index=d.index,
            start_t=d.start_t,
            bottom_t=d.bottom_t,
            end_t=d.end_t,
            accepted=d.reason is None,
            reason=d.reason,
            max_kick_hip_angle=r_angle(FULL_EXTENSION_DEG - d.min_angle),
            knee_angle_at_top=r_opt_angle(d.form_at_bottom),
            min_arm_support_angle=r_opt_angle(d.min_hold),
            invalid_ratio=r_ratio(d.invalid_ratio),
        )


register_counter("DONKEY_KICK", DonkeyKickCounter.from_config)
