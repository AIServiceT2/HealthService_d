"""무작위 동작 확인 (SPEC 6장).

- 발급(`issue_challenge`)만 `secrets`로 무작위 선택한다. 판정은 결정적이다.
- 코(얼굴 랜드마크)는 서버로 받지 않으므로 머리 높이를 어깨로 추정한다 (DECISIONS D-02):
  머리 높이 y = 어깨 중점 y − head_height_ratio × 어깨 너비
  손을 들었다 = 손목 y < 머리 높이 y − hand_above_head_margin × 어깨 너비 (픽셀, y는 아래로 증가)
- 어깨 너비를 기준으로 쓰므로 **카메라를 정면으로 보고** 해야 한다
  (측면이면 어깨 너비가 0에 가까움).
- 유지 시간은 같은 조건이 끊김 없이 이어진 프레임의 첫 시각부터 잰다(ms). 무효 프레임은 끊김.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable

from rep_engine.adapters import Point, SkeletonFrame
from rep_engine.config import LivenessCfg
from rep_engine.features.geometry import distance
from rep_engine.landmarks import Joint
from rep_engine.rounding import r_ratio
from rep_engine.schemas import (
    IssuedChallenge,
    LivenessAction,
    LivenessChallenge,
    LivenessEvidence,
    LivenessResult,
    LivenessStatus,
)

INSTRUCTIONS: dict[LivenessAction, str] = {
    LivenessAction.RAISE_LEFT_HAND: "왼손을 머리 위로 들어 주세요",
    LivenessAction.RAISE_RIGHT_HAND: "오른손을 머리 위로 들어 주세요",
    LivenessAction.RAISE_BOTH_HANDS: "양손을 머리 위로 들어 주세요",
}

_CHALLENGE_ID_BYTES = 12


def issue_challenge() -> IssuedChallenge:
    """무작위 동작 1개를 발급한다 (`secrets` 사용, 판정과 분리)."""
    action = secrets.choice(list(LivenessAction))
    return IssuedChallenge(
        action=action,
        instruction=INSTRUCTIONS[action],
        challenge_id=secrets.token_hex(_CHALLENGE_ID_BYTES),
    )


def _hands_raised(
    joints: tuple[Point | None, ...], cfg: LivenessCfg, min_visibility: float
) -> tuple[bool, bool] | None:
    """(왼손 듦, 오른손 듦). 어깨가 안 보이면 None(판정 불가 프레임)."""
    ls, rs = joints[Joint.LEFT_SHOULDER], joints[Joint.RIGHT_SHOULDER]
    if ls is None or rs is None or ls.vis < min_visibility or rs.vis < min_visibility:
        return None
    width = distance((ls.x, ls.y), (rs.x, rs.y))
    if width == 0.0:
        return None
    head_y = (ls.y + rs.y) / 2.0 - cfg.head_height_ratio * width
    limit_y = head_y - cfg.hand_above_head_margin * width

    def up(w: Point | None) -> bool:
        return w is not None and w.vis >= min_visibility and w.y < limit_y

    return up(joints[Joint.LEFT_WRIST]), up(joints[Joint.RIGHT_WRIST])


class LivenessEvaluator:
    """스트리밍 판정기. `update`가 결과를 돌려주면 판정이 끝난 것이다."""

    def __init__(
        self, challenge: LivenessChallenge, cfg: LivenessCfg, min_visibility: float
    ) -> None:
        self.challenge = challenge
        self._cfg = cfg
        self._min_vis = min_visibility
        self._total = 0
        self._valid = 0
        self._hold_start: int | None = None
        self._wrong_start: int | None = None
        self._max_hold = 0
        self._max_wrong = 0
        self._result: LivenessResult | None = None

    @property
    def done(self) -> bool:
        return self._result is not None

    def _make(self, status: LivenessStatus, passed_at: int | None) -> LivenessResult:
        ratio = self._valid / self._total if self._total else 0.0
        return LivenessResult(
            challenge_id=self.challenge.challenge_id,
            action=self.challenge.action,
            status=status,
            passed_at_t=passed_at,
            evidence=LivenessEvidence(
                max_hold_ms=self._max_hold,
                wrong_hand_max_hold_ms=self._max_wrong,
                valid_frame_ratio=r_ratio(ratio),
                wrong_hand_detected=self._max_wrong >= self._cfg.wrong_hand_hold_ms,
            ),
        )

    def update(self, frame: SkeletonFrame) -> LivenessResult | None:
        """프레임 1개 처리. 통과했거나 만료 시각이 지나면 최종 결과를 돌려준다."""
        if self._result is not None:
            return self._result
        ch = self.challenge
        if frame.t < ch.issued_at_t:
            return None
        if frame.t > ch.expires_at_t:
            return self.finish()
        self._total += 1
        raised = (
            None if frame.joints is None else _hands_raised(frame.joints, self._cfg, self._min_vis)
        )
        if raised is None:
            self._hold_start = None
            self._wrong_start = None
            return None
        self._valid += 1
        left, right = raised
        action = ch.action
        if action is LivenessAction.RAISE_LEFT_HAND:
            ok, wrong = left, right and not left
        elif action is LivenessAction.RAISE_RIGHT_HAND:
            ok, wrong = right, left and not right
        else:
            ok, wrong = left and right, False

        if wrong:
            self._wrong_start = frame.t if self._wrong_start is None else self._wrong_start
            self._max_wrong = max(self._max_wrong, frame.t - self._wrong_start)
        else:
            self._wrong_start = None

        if not ok:
            self._hold_start = None
            return None
        self._hold_start = frame.t if self._hold_start is None else self._hold_start
        hold = frame.t - self._hold_start
        self._max_hold = max(self._max_hold, hold)
        if hold >= self._cfg.liveness_hold_ms:
            self._result = self._make(LivenessStatus.PASSED, frame.t)
        return self._result

    def finish(self) -> LivenessResult:
        """입력이 끝났을 때 최종 결과 (통과 못 했으면 EXPIRED 또는 FAILED_NO_PERSON)."""
        if self._result is None:
            ratio = self._valid / self._total if self._total else 0.0
            status = (
                LivenessStatus.FAILED_NO_PERSON
                if ratio < self._cfg.min_valid_ratio
                else LivenessStatus.EXPIRED
            )
            self._result = self._make(status, None)
        return self._result


def evaluate_liveness(
    challenge: LivenessChallenge,
    frames: Iterable[SkeletonFrame],
    cfg: LivenessCfg,
    min_visibility: float,
) -> LivenessResult:
    """배치 판정 = 스트리밍 반복. 구간은 issuedAtT ≤ t ≤ expiresAtT."""
    ev = LivenessEvaluator(challenge, cfg, min_visibility)
    for fr in frames:
        if ev.update(fr) is not None:
            break
    return ev.finish()
