"""poseSummary와 자세 오류 태그 (SPEC 8.1·8.2, L4 입력).

스쿼트는 `pose_summary`, 푸시업·윗몸 일으키기는 `pushup_pose_summary`·`situp_pose_summary`.

인정 렙의 최저점 값(RepEvent, 이미 반올림된 값)으로만 계산한다. 그래서 기기와 서버가 같은
RepEvent 목록을 가지면 요약도 같다. 각도·시간은 소수 1자리.
"""

from __future__ import annotations

from collections.abc import Sequence

from rep_engine.config import FormTagsCfg, PushupCfg
from rep_engine.rounding import r_angle, r_ms
from rep_engine.schemas import (
    AvgMax,
    AvgMinMax,
    AvgOnly,
    AvgStd,
    FormTag,
    PoseSummary,
    PushupPoseSummary,
    PushupRepEvent,
    RepEvent,
    RepReason,
    SitupPoseSummary,
    SitupRepEvent,
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


# --- 푸시업·윗몸 일으키기 ----------------------------------------------------
_TAG_ORDER = {tag: i for i, tag in enumerate(FormTag)}


def _reason_tags(reps: Sequence[PushupRepEvent | SitupRepEvent], cfg: FormTagsCfg) -> list[FormTag]:
    """미인정 사유 비율로 정하는 태그 (스쿼트 `form_tags`와 같은 기준값)."""
    n = len(reps)
    if not n:
        return []

    def ratio(reason: RepReason) -> float:
        return sum(1 for e in reps if e.reason is reason) / n

    tags: list[FormTag] = []
    if ratio(RepReason.SHALLOW_DEPTH) > cfg.shallow_ratio:
        tags.append(FormTag.SHALLOW_DEPTH_FREQUENT)
    if ratio(RepReason.TOO_FAST) > cfg.too_fast_ratio:
        tags.append(FormTag.TEMPO_TOO_FAST)
    if ratio(RepReason.OUT_OF_FRAME) > cfg.out_of_frame_ratio:
        tags.append(FormTag.FREQUENT_OUT_OF_FRAME)
    return tags


def _ordered(tags: list[FormTag]) -> list[FormTag]:
    """FormTag 정의 순서로 정렬."""
    return sorted(tags, key=_TAG_ORDER.__getitem__)


def _duration(acc: Sequence[PushupRepEvent | SitupRepEvent]) -> AvgStd:
    dur = [float(e.end_t - e.start_t) for e in acc]
    return AvgStd(avg=r_ms(mean(dur)), std=r_ms(pstdev(dur)))


def _flexion(mins: Sequence[float]) -> AvgMinMax:
    flex = [FULL_EXTENSION_DEG - a for a in mins]
    return AvgMinMax(avg=r_angle(mean(flex)), min=r_angle(min(flex)), max=r_angle(max(flex)))


def pushup_pose_summary(
    reps: Sequence[PushupRepEvent], cfg: FormTagsCfg, pushup: PushupCfg
) -> PushupPoseSummary:
    """시도 렙 전체로 사유 태그를, 인정 렙으로 수치와 자세 태그를 만든다."""
    tags = _reason_tags(reps, cfg)
    acc = [e for e in reps if e.accepted]
    if not acc:
        return PushupPoseSummary(
            elbow_flexion_deg=None,
            body_line_dev_deg=None,
            elbow_asymmetry_deg=None,
            rep_duration_ms=None,
            depth_consistency_deg=None,
            form_tags=_ordered(tags),
        )
    depth_std = r_angle(pstdev([e.min_elbow_angle for e in acc]))
    line = [e.body_line_dev_at_bottom for e in acc if e.body_line_dev_at_bottom is not None]
    asym = [e.elbow_asymmetry_at_bottom for e in acc if e.elbow_asymmetry_at_bottom is not None]
    line_avg = r_angle(mean(line)) if line else None
    asym_avg = r_angle(mean(asym)) if asym else None
    if depth_std > cfg.depth_std_deg:
        tags.append(FormTag.DEPTH_INCONSISTENT)
    if line_avg is not None and line_avg > pushup.body_line_dev_deg:
        tags.append(FormTag.BODY_LINE_BROKEN)
    if asym_avg is not None and asym_avg > cfg.asymmetry_deg:
        tags.append(FormTag.ELBOW_ASYMMETRY)
    return PushupPoseSummary(
        elbow_flexion_deg=_flexion([e.min_elbow_angle for e in acc]),
        body_line_dev_deg=AvgMax(avg=line_avg, max=r_angle(max(line)))
        if line_avg is not None
        else None,
        elbow_asymmetry_deg=AvgOnly(avg=asym_avg) if asym_avg is not None else None,
        rep_duration_ms=_duration(acc),
        depth_consistency_deg=depth_std,
        form_tags=_ordered(tags),
    )


def situp_pose_summary(reps: Sequence[SitupRepEvent], cfg: FormTagsCfg) -> SitupPoseSummary:
    """시도 렙 전체로 사유 태그를, 인정 렙으로 수치를 만든다."""
    tags = _reason_tags(reps, cfg)
    acc = [e for e in reps if e.accepted]
    if not acc:
        return SitupPoseSummary(
            torso_raise_deg=None,
            hip_flexion_deg=None,
            knee_angle_deg=None,
            rep_duration_ms=None,
            depth_consistency_deg=None,
            form_tags=_ordered(tags),
        )
    depth_std = r_angle(pstdev([e.min_torso_angle for e in acc]))
    hips = [e.min_hip_angle for e in acc if e.min_hip_angle is not None]
    knee = [e.knee_angle_at_bottom for e in acc if e.knee_angle_at_bottom is not None]
    if depth_std > cfg.depth_std_deg:
        tags.append(FormTag.DEPTH_INCONSISTENT)
    return SitupPoseSummary(
        torso_raise_deg=_flexion([e.min_torso_angle for e in acc]),
        hip_flexion_deg=_flexion(hips) if hips else None,
        knee_angle_deg=AvgOnly(avg=r_angle(mean(knee))) if knee else None,
        rep_duration_ms=_duration(acc),
        depth_consistency_deg=depth_std,
        form_tags=_ordered(tags),
    )
