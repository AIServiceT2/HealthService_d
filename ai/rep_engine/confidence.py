"""세션 확신도 (SPEC 7장).

원시 점수 (모두 0~1):
- c_vis: 활성 구간 유효 프레임의 핵심 관절 평균 가시도
- c_valid: 활성 구간 유효 프레임 비율
- c_track: 1 − (무효 연속 구간 총 시간 / 활성 구간 시간)
- c_consistency: 인정 렙의 렙 시간 변동계수(CV)와 최저 판정 각도(`depth_angle`) 표준편차를
  각각 exp(−k·x)로 바꿔 평균.
  인정 렙이 `min_reps_for_consistency` 미만이면 `neutral_score`.
- c_unaccepted: 1 − (시도 렙 중 OUT_OF_FRAME 비율). 시도 렙 0개면 `neutral_score`.

raw = Σ wᵢ·cᵢ. 무작위 동작 확인이 PASSED가 아니면(없는 경우 포함) `liveness_penalty`를 곱한다.
최종 aiConfidence = 카탈로그 `calibration` 구간 선형 매핑(raw).

활성 구간: 시작 = liveness 통과 시각(없으면 첫 프레임),
끝 = 마지막 렙 endT(렙이 없으면 마지막 프레임).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from rep_engine.adapters import SkeletonFrame
from rep_engine.config import ConfidenceCfg
from rep_engine.features.extractor import frame_quality
from rep_engine.rounding import r_ratio
from rep_engine.schemas import (
    AnyRepEvent,
    ConfidenceComponents,
    ConfidenceResult,
    LivenessResult,
    LivenessStatus,
    RepReason,
)
from rep_engine.stats import mean, pstdev


def apply_calibration(raw: float, points: Sequence[tuple[float, float]]) -> float:
    """구간 선형 보정. points는 raw 오름차순, raw 0과 1을 포함한다."""
    x = min(1.0, max(0.0, raw))
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]  # pragma: no cover  (검증된 점 목록에서는 도달하지 않음)


def _tracking(frames: Sequence[SkeletonFrame], valid: Sequence[bool], end_t: int) -> float:
    """무효 연속 구간 총 시간(ms). 구간 길이 = 다음 유효 프레임(없으면 끝) − 첫 무효 프레임."""
    total = 0
    run_start: int | None = None
    for fr, ok in zip(frames, valid, strict=True):
        if not ok and run_start is None:
            run_start = fr.t
        elif ok and run_start is not None:
            total += fr.t - run_start
            run_start = None
    if run_start is not None:
        total += max(0, end_t - run_start)
    return float(total)


#: (프레임, min_visibility) → (유효 프레임 여부, 판정 관절 평균 가시도). 종목마다 판정 관절이 다르다
QualityFn = Callable[[SkeletonFrame, float], tuple[bool, float | None]]


def _consistency(accepted: Sequence[AnyRepEvent], cfg: ConfidenceCfg) -> float:
    if len(accepted) < cfg.min_reps_for_consistency:
        return cfg.neutral_score
    durations = [float(e.end_t - e.start_t) for e in accepted]
    depths = [e.depth_angle for e in accepted]
    m = mean(durations)
    cv = pstdev(durations) / m if m > 0 else 0.0
    s_dur = math.exp(-cfg.consistency_k.duration_cv * cv)
    s_depth = math.exp(-cfg.consistency_k.depth_std * pstdev(depths))
    return (s_dur + s_depth) / 2.0


def compute_confidence(
    frames: Sequence[SkeletonFrame],
    reps: Sequence[AnyRepEvent],
    liveness: LivenessResult | None,
    cfg: ConfidenceCfg,
    min_visibility: float,
    quality_fn: QualityFn = frame_quality,
) -> ConfidenceResult:
    """세션 확신도를 계산한다. `frames`는 세션 전체 공통 골격 프레임(시각순).

    `quality_fn`의 기본값은 스쿼트(다리 관절) 기준이다.
    """
    passed = liveness is not None and liveness.status is LivenessStatus.PASSED
    start_t: int | None = None
    end_t: int | None = None
    if frames:
        start_t = (
            liveness.passed_at_t
            if passed and liveness is not None and liveness.passed_at_t is not None
            else frames[0].t
        )
        end_t = reps[-1].end_t if reps else frames[-1].t
    window = (
        [f for f in frames if start_t <= f.t <= end_t]
        if start_t is not None and end_t is not None
        else []
    )

    quality = [quality_fn(f, min_visibility) for f in window]
    valid = [q[0] for q in quality]
    vis_vals = [q[1] for q in quality if q[1] is not None]
    c_vis = mean(vis_vals) if vis_vals else 0.0
    c_valid = sum(valid) / len(valid) if valid else 0.0
    duration = (end_t - start_t) if (start_t is not None and end_t is not None) else 0
    if duration > 0 and end_t is not None:
        c_track = max(0.0, 1.0 - _tracking(window, valid, end_t) / duration)
    else:
        c_track = 1.0 if valid and all(valid) else 0.0

    accepted = [e for e in reps if e.accepted]
    c_cons = _consistency(accepted, cfg)
    if reps:
        oof = sum(1 for e in reps if e.reason is RepReason.OUT_OF_FRAME)
        c_unacc = 1.0 - oof / len(reps)
    else:
        c_unacc = cfg.neutral_score

    w = cfg.weights
    raw = (
        w.vis * c_vis
        + w.valid * c_valid
        + w.track * c_track
        + w.consistency * c_cons
        + w.unaccepted * c_unacc
    )
    if not passed:
        raw *= cfg.liveness_penalty
    raw = min(1.0, max(0.0, raw))
    calibrated = apply_calibration(raw, cfg.calibration)
    return ConfidenceResult(
        ai_confidence=r_ratio(calibrated),
        components=ConfidenceComponents(
            vis=r_ratio(c_vis),
            valid=r_ratio(c_valid),
            track=r_ratio(c_track),
            consistency=r_ratio(c_cons),
            unaccepted=r_ratio(c_unacc),
            raw=r_ratio(raw),
            liveness_penalty_applied=not passed,
            active_start_t=start_t,
            active_end_t=end_t,
        ),
    )
