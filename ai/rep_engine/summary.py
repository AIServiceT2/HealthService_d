"""poseSummary와 자세 오류 태그 (SPEC 8.1·8.2, L4 입력).

인정 렙의 최저점 값(RepEvent, 이미 반올림된 값)으로만 계산한다. 그래서 기기와 서버가 같은
RepEvent 목록을 가지면 요약도 같다. 각도·시간은 소수 1자리.
"""

from __future__ import annotations

from collections.abc import Sequence

from rep_engine.config import FormTagsCfg
from rep_engine.rounding import r_angle, r_ms
from rep_engine.schemas import (
    AvgMax,
    AvgMinMax,
    AvgOnly,
    AvgStd,
    FormTag,
    PoseSummary,
    RepEvent,
    RepReason,
)
from rep_engine.stats import mean, pstdev

FULL_EXTENSION_DEG = 180.0  # kneeFlexion = 180 − kneeAngle (정의상 상수)


def form_tags(
    reps: Sequence[RepEvent],
    depth_consistency: float | None,
    trunk_avg: float | None,
    asym_avg: float | None,
    cfg: FormTagsCfg,
) -> list[FormTag]:
    """기준을 넘은 자세 오류 태그 (FormTag 정의 순서)."""
    tags: list[FormTag] = []
    n = len(reps)

    def ratio(reason: RepReason) -> float:
        return sum(1 for e in reps if e.reason is reason) / n if n else 0.0

    if n and ratio(RepReason.SHALLOW_DEPTH) > cfg.shallow_ratio:
        tags.append(FormTag.SHALLOW_DEPTH_FREQUENT)
    if depth_consistency is not None and depth_consistency > cfg.depth_std_deg:
        tags.append(FormTag.DEPTH_INCONSISTENT)
    if trunk_avg is not None and trunk_avg > cfg.trunk_lean_deg:
        tags.append(FormTag.TRUNK_LEAN_EXCESSIVE)
    if asym_avg is not None and asym_avg > cfg.asymmetry_deg:
        tags.append(FormTag.KNEE_ASYMMETRY)
    if n and ratio(RepReason.TOO_FAST) > cfg.too_fast_ratio:
        tags.append(FormTag.TEMPO_TOO_FAST)
    if n and ratio(RepReason.OUT_OF_FRAME) > cfg.out_of_frame_ratio:
        tags.append(FormTag.FREQUENT_OUT_OF_FRAME)
    return tags


def pose_summary(reps: Sequence[RepEvent], cfg: FormTagsCfg) -> PoseSummary:
    """시도 렙 전체로 태그를, 인정 렙으로 수치를 만든다."""
    acc = [e for e in reps if e.accepted]
    if not acc:
        return PoseSummary(
            knee_flexion_deg=None,
            trunk_lean_deg=None,
            knee_asymmetry_deg=None,
            rep_duration_ms=None,
            depth_consistency_deg=None,
            form_tags=form_tags(reps, None, None, None, cfg),
        )
    flex = [FULL_EXTENSION_DEG - e.min_knee_angle for e in acc]
    trunk = [e.trunk_lean_at_bottom for e in acc if e.trunk_lean_at_bottom is not None]
    asym = [e.knee_asymmetry_at_bottom for e in acc if e.knee_asymmetry_at_bottom is not None]
    dur = [float(e.end_t - e.start_t) for e in acc]
    depth_std = r_angle(pstdev([e.min_knee_angle for e in acc]))
    trunk_avg = r_angle(mean(trunk)) if trunk else None
    asym_avg = r_angle(mean(asym)) if asym else None
    return PoseSummary(
        knee_flexion_deg=AvgMinMax(
            avg=r_angle(mean(flex)), min=r_angle(min(flex)), max=r_angle(max(flex))
        ),
        trunk_lean_deg=AvgMax(avg=trunk_avg, max=r_angle(max(trunk)))
        if trunk_avg is not None
        else None,
        knee_asymmetry_deg=AvgOnly(avg=asym_avg) if asym_avg is not None else None,
        rep_duration_ms=AvgStd(avg=r_ms(mean(dur)), std=r_ms(pstdev(dur))),
        depth_consistency_deg=depth_std,
        form_tags=form_tags(reps, depth_std, trunk_avg, asym_avg, cfg),
    )
