"""스쿼트 렙 판정 상태 머신 (SPEC 5장).

상태: STANDING → DESCENDING → ASCENDING → STANDING
(+ WAIT_STAND: 렙을 폐기했거나 화면 이탈로 끊은 뒤, 다시 설 때까지 기다리는 상태)

판정 각도는 `FrameFeatures.knee_angle`(필터 적용 무릎 내각, 도). 시간 규칙은 모두 ms 기반이라
프레임레이트와 무관하다. 모바일 포팅을 위해 if/else와 숫자 연산만 쓴다.

미인정 사유는 우선순위 OUT_OF_FRAME > TOO_FAST > SHALLOW_DEPTH 중 하나만 붙인다.
"""

from __future__ import annotations

from rep_engine.config import EngineConfig, SquatCfg
from rep_engine.counters.base import ExerciseCounter, register_counter
from rep_engine.features.extractor import FrameFeatures
from rep_engine.rounding import r_angle, r_opt_angle, r_opt_ratio, r_ratio
from rep_engine.schemas import RepEvent, RepReason

STANDING = "STANDING"
DESCENDING = "DESCENDING"
ASCENDING = "ASCENDING"
WAIT_STAND = "WAIT_STAND"


class SquatCounter(ExerciseCounter):
    """스쿼트 판정기."""

    def __init__(self, cfg: SquatCfg) -> None:
        self._cfg = cfg
        self._state = STANDING
        self._angle: float | None = None
        self._accepted = 0
        self._index = 0
        # 진행 중인 렙
        self._start_t = 0
        self._min_angle = 0.0
        self._min_t = 0
        self._trunk_at_min: float | None = None
        self._asym_at_min: float | None = None
        self._max_hip_drop: float | None = None
        self._n_total = 0
        self._n_invalid = 0
        self._last_valid_t = 0

    @classmethod
    def from_config(cls, cfg: EngineConfig) -> SquatCounter:
        return cls(cfg.squat)

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_angle(self) -> float | None:
        return self._angle

    @property
    def accepted_count(self) -> int:
        return self._accepted

    # --- 내부 ----------------------------------------------------------------
    def _begin(self, f: FrameFeatures, angle: float) -> None:
        self._state = DESCENDING
        self._start_t = f.t
        self._min_angle = angle
        self._min_t = f.t
        self._trunk_at_min = f.trunk_lean
        self._asym_at_min = f.knee_asymmetry
        self._max_hip_drop = f.hip_drop
        self._n_total = 1
        self._n_invalid = 0
        self._last_valid_t = f.t

    def _new_min(self, f: FrameFeatures, angle: float) -> None:
        self._min_angle = angle
        self._min_t = f.t
        self._trunk_at_min = f.trunk_lean
        self._asym_at_min = f.knee_asymmetry

    def _depth_ok(self) -> bool:
        c = self._cfg
        if self._min_angle <= c.depth_accept_angle:
            return True
        return (
            c.depth_mode == "angle_or_hip_drop"
            and self._max_hip_drop is not None
            and self._max_hip_drop >= c.hip_drop_accept
        )

    def _close(self, end_t: int, out_of_frame: bool) -> list[RepEvent]:
        """렙을 끝낸다. 시도 각도에 못 미쳤으면 아무것도 기록하지 않는다."""
        c = self._cfg
        if self._min_angle >= c.attempt_angle:
            return []
        invalid_ratio = self._n_invalid / self._n_total if self._n_total else 0.0
        reason: RepReason | None
        if out_of_frame or invalid_ratio > c.max_invalid_ratio_in_rep:
            reason = RepReason.OUT_OF_FRAME
        elif end_t - self._start_t < c.min_rep_ms or self._min_t - self._start_t < c.min_descent_ms:
            reason = RepReason.TOO_FAST
        elif not self._depth_ok():
            reason = RepReason.SHALLOW_DEPTH
        else:
            reason = None
        self._index += 1
        if reason is None:
            self._accepted += 1
        return [
            RepEvent(
                index=self._index,
                start_t=self._start_t,
                bottom_t=self._min_t,
                end_t=end_t,
                accepted=reason is None,
                reason=reason,
                min_knee_angle=r_angle(self._min_angle),
                max_hip_drop=r_opt_ratio(self._max_hip_drop),
                trunk_lean_at_bottom=r_opt_angle(self._trunk_at_min),
                knee_asymmetry_at_bottom=r_opt_angle(self._asym_at_min),
                invalid_ratio=r_ratio(invalid_ratio),
            )
        ]

    # --- 공개 ----------------------------------------------------------------
    def update(self, features: FrameFeatures) -> list[RepEvent]:
        """프레임 1개 처리. 이번 프레임에서 끝난 렙(0~1개)을 돌려준다."""
        c = self._cfg
        f = features
        angle = f.knee_angle if f.valid else None
        if angle is not None:
            self._angle = angle

        if self._state == STANDING:
            if angle is not None and angle < c.descent_start_angle:
                self._begin(f, angle)
            return []

        if self._state == WAIT_STAND:
            if angle is not None and angle >= c.stand_angle:
                self._state = STANDING
            return []

        # DESCENDING / ASCENDING: 렙 진행 중
        self._n_total += 1
        if angle is None:
            self._n_invalid += 1
            if f.t - self._last_valid_t > c.max_gap_in_rep_ms:
                self._state = WAIT_STAND
                return self._close(end_t=self._last_valid_t, out_of_frame=True)
            return []

        if f.t - self._start_t > c.max_rep_ms:
            self._state = WAIT_STAND  # 렙 폐기 (기록 없음)
            return []

        self._last_valid_t = f.t
        if f.hip_drop is not None and (
            self._max_hip_drop is None or f.hip_drop > self._max_hip_drop
        ):
            self._max_hip_drop = f.hip_drop

        if angle >= c.stand_angle:
            self._state = STANDING
            return self._close(end_t=f.t, out_of_frame=False)

        if self._state == DESCENDING:
            if angle < self._min_angle:
                self._new_min(f, angle)
            elif angle >= self._min_angle + c.bottom_hysteresis_deg:
                self._state = ASCENDING
        elif angle < self._min_angle:  # ASCENDING 중 다시 내려가 최저값 갱신
            self._new_min(f, angle)
            self._state = DESCENDING
        return []


register_counter("SQUAT", SquatCounter.from_config)
