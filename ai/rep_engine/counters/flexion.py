"""굽혔다 펴는 렙 판정 상태 머신 (푸시업·윗몸 일으키기 공통).

스쿼트 상태 머신(`squat.py`, SPEC 5장)과 같은 규칙을 판정 각도 하나로 일반화했다.
엉덩이 하강(hipDrop) 같은 스쿼트 전용 깊이 판정은 없다.

둘째 판정 각도(`ChainFeatures.aux_angle`)를 쓰는 종목(윗몸 일으키기)은 `_aux_accept_angle`을 정한다.
그러면 렙 동안 둘째 각도의 최저값도 그 기준 이하여야 인정한다 (D-70). 렙 동안 둘째 각도가 한 번도
안 보였으면 OUT_OF_FRAME, 기준을 못 넘었으면 SHALLOW_DEPTH.

자세 확인(`_posture_limit`, 푸시업)을 쓰는 종목은 자세 각도(`ChainFeatures.posture_angle`)가 보이고
기준 이하일 때만 렙을 시작한다. 최저점의 자세 각도가 기준을 넘거나 보이지 않으면 그 렙은
기록하지 않는다 (시도로도 세지 않음).
그 종목 자세가 아닐 때의 팔 움직임을 세지 않기 위해서다 (D-71).

상태: REST → FLEXING → EXTENDING → REST
(+ WAIT_REST: 렙을 폐기했거나 화면 이탈로 끊은 뒤, 다시 쉬는 자세가 될 때까지 기다리는 상태)

판정 각도는 `ChainFeatures.angle`(필터 적용 내각, 도). 쉬는 자세에서 크고 굽힐수록 작아진다.
미인정 사유 우선순위는 스쿼트와 같다: OUT_OF_FRAME > TOO_FAST > SHALLOW_DEPTH.
종목별 렙 결과 모양은 하위 클래스의 `_event`가 정한다.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from rep_engine.config import FlexionCfg
from rep_engine.counters.base import ExerciseCounter
from rep_engine.features.chain import ChainFeatures
from rep_engine.schemas import AnyRepEvent, RepReason

REST = "REST"
FLEXING = "FLEXING"
EXTENDING = "EXTENDING"
WAIT_REST = "WAIT_REST"


@dataclass(frozen=True, slots=True)
class RepDraft:
    """확정된 렙의 종목 공통 값. 하위 클래스가 이걸로 종목별 렙 결과를 만든다."""

    index: int
    start_t: int
    bottom_t: int
    end_t: int
    reason: RepReason | None
    min_angle: float
    #: 렙 동안 둘째 판정 각도의 최저값 (쓰지 않거나 한 번도 안 보였으면 None)
    min_aux: float | None
    #: 최저점에서의 좌우 차·보조 각도 (필터 전)
    asymmetry_at_bottom: float | None
    form_at_bottom: float | None
    invalid_ratio: float


class FlexionCounter(ExerciseCounter[ChainFeatures]):
    """굽혔다 펴는 종목 판정기의 공통 부분."""

    def __init__(self, cfg: FlexionCfg) -> None:
        self._cfg = cfg
        self._state = REST
        self._angle: float | None = None
        self._accepted = 0
        self._index = 0
        # 진행 중인 렙
        self._start_t = 0
        self._min_angle = 0.0
        self._min_t = 0
        self._asym_at_min: float | None = None
        self._form_at_min: float | None = None
        self._posture_at_min: float | None = None
        self._min_aux: float | None = None
        self._n_total = 0
        self._n_invalid = 0
        self._last_valid_t = 0
        # 시도 각도 전에 화면 밖으로 나간 렙: 다시 나타날 때 깊이 굽혀 있으면 OUT_OF_FRAME
        self._pending_oof = False

    @abstractmethod
    def _event(self, d: RepDraft) -> AnyRepEvent:
        """종목별 렙 결과 (반올림 포함)."""

    @property
    def _aux_accept_angle(self) -> float | None:
        """둘째 판정 각도의 인정 기준 (이하여야 인정). None이면 둘째 조건 없음."""
        return None

    @property
    def _posture_limit(self) -> float | None:
        """자세 각도 기준 (이하여야 렙으로 셈). None이면 자세 확인 없음."""
        return None

    def _can_start(self, f: ChainFeatures) -> bool:
        limit = self._posture_limit
        return limit is None or (f.posture_angle is not None and f.posture_angle <= limit)

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
    def _begin(self, f: ChainFeatures, angle: float) -> None:
        self._state = FLEXING
        self._start_t = f.t
        self._n_total = 1
        self._n_invalid = 0
        self._last_valid_t = f.t
        self._min_aux = None
        self._track_aux(f)
        self._new_min(f, angle)

    def _track_aux(self, f: ChainFeatures) -> None:
        if f.aux_angle is not None and (self._min_aux is None or f.aux_angle < self._min_aux):
            self._min_aux = f.aux_angle

    def _new_min(self, f: ChainFeatures, angle: float) -> None:
        self._min_angle = angle
        self._min_t = f.t
        self._asym_at_min = f.asymmetry
        self._form_at_min = f.form_angle
        self._posture_at_min = f.posture_angle

    def _close(
        self, end_t: int, out_of_frame: bool, require_attempt: bool = True
    ) -> list[AnyRepEvent]:
        """렙을 끝낸다. 시도 각도에 못 미쳤으면(require_attempt) 아무것도 기록하지 않는다."""
        c = self._cfg
        if require_attempt and self._min_angle >= c.attempt_angle:
            return []
        limit = self._posture_limit
        if limit is not None and (self._posture_at_min is None or self._posture_at_min > limit):
            return []  # 최저점이 그 종목 자세가 아니거나 확인할 수 없음 → 기록하지 않음
        invalid_ratio = self._n_invalid / self._n_total if self._n_total else 0.0
        aux_limit = self._aux_accept_angle
        aux_missing = aux_limit is not None and self._min_aux is None
        aux_shallow = (
            aux_limit is not None and self._min_aux is not None and self._min_aux > aux_limit
        )
        reason: RepReason | None
        if out_of_frame or invalid_ratio > c.max_invalid_ratio_in_rep or aux_missing:
            reason = RepReason.OUT_OF_FRAME
        elif end_t - self._start_t < c.min_rep_ms or self._min_t - self._start_t < c.min_descent_ms:
            reason = RepReason.TOO_FAST
        elif self._min_angle > c.depth_accept_angle or aux_shallow:
            reason = RepReason.SHALLOW_DEPTH
        else:
            reason = None
        self._index += 1
        if reason is None:
            self._accepted += 1
        return [
            self._event(
                RepDraft(
                    index=self._index,
                    start_t=self._start_t,
                    bottom_t=self._min_t,
                    end_t=end_t,
                    reason=reason,
                    min_angle=self._min_angle,
                    min_aux=self._min_aux,
                    asymmetry_at_bottom=self._asym_at_min,
                    form_at_bottom=self._form_at_min,
                    invalid_ratio=invalid_ratio,
                )
            )
        ]

    # --- 공개 ----------------------------------------------------------------
    def update(self, features: ChainFeatures) -> list[AnyRepEvent]:
        """프레임 1개 처리. 이번 프레임에서 끝난 렙(0~1개)을 돌려준다."""
        c = self._cfg
        f = features
        angle = f.angle if f.valid else None
        if angle is not None:
            self._angle = angle

        if self._state == REST:
            if angle is not None and angle < c.flex_start_angle and self._can_start(f):
                self._begin(f, angle)
            return []

        if self._state == WAIT_REST:
            events: list[AnyRepEvent] = []
            if angle is not None and self._pending_oof:
                # 굽히는 중 화면 밖으로 나갔다가 시도 각도 아래로 굽힌 채 다시 나타남 → 가려진 렙
                self._pending_oof = False
                if angle < c.attempt_angle:
                    events = self._close(
                        end_t=self._last_valid_t, out_of_frame=True, require_attempt=False
                    )
            if angle is not None and angle >= c.rest_angle:
                self._state = REST
            return events

        # FLEXING / EXTENDING: 렙 진행 중
        self._n_total += 1
        if angle is None:
            self._n_invalid += 1
            if f.t - self._last_valid_t > c.max_gap_in_rep_ms:
                self._state = WAIT_REST
                self._pending_oof = self._min_angle >= c.attempt_angle
                return self._close(end_t=self._last_valid_t, out_of_frame=True)
            return []

        if f.t - self._start_t > c.max_rep_ms:
            self._state = WAIT_REST  # 렙 폐기 (기록 없음)
            self._pending_oof = False
            return []

        self._last_valid_t = f.t
        self._track_aux(f)
        if angle >= c.rest_angle:
            self._state = REST
            return self._close(end_t=f.t, out_of_frame=False)

        if self._state == FLEXING:
            if angle < self._min_angle:
                self._new_min(f, angle)
            elif angle >= self._min_angle + c.bottom_hysteresis_deg:
                self._state = EXTENDING
        elif angle < self._min_angle:  # EXTENDING 중 다시 굽혀 최저값 갱신
            self._new_min(f, angle)
            self._state = FLEXING
        return []
