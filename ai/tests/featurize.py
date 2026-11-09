"""테스트용: 합성 설정 → 공통 골격 → 프레임 특징."""

from __future__ import annotations

from rep_engine.adapters import SkeletonFrame, adapter_for_model_version
from rep_engine.config import EngineConfig
from rep_engine.features.extractor import FeatureExtractor, FrameFeatures
from rep_engine.schemas import RepEvent, RepReason
from tools.synth import SynthConfig, synth_frames, synth_meta


def skeletons(sc: SynthConfig) -> list[SkeletonFrame]:
    meta = synth_meta(sc)
    adapter = adapter_for_model_version(meta.device.model_version)
    return [
        adapter.to_skeleton(f, meta.image_width, meta.image_height, meta.mirrored)
        for f in synth_frames(sc)
    ]


def features(sc: SynthConfig, cfg: EngineConfig) -> list[FrameFeatures]:
    ex = FeatureExtractor(cfg.features, cfg.squat.stand_angle)
    return [ex.update(s) for s in skeletons(sc)]


def reps_for(sc: SynthConfig, cfg: EngineConfig) -> list[RepEvent]:
    from rep_engine.counters.squat import SquatCounter

    return SquatCounter(cfg.squat).run(features(sc, cfg))


def make_rep(
    index: int = 1,
    start: int = 0,
    dur: int = 2000,
    min_angle: float = 85.0,
    reason: RepReason | None = None,
    trunk: float | None = 20.0,
    asym: float | None = 2.0,
) -> RepEvent:
    return RepEvent(
        index=index,
        start_t=start,
        bottom_t=start + dur // 2,
        end_t=start + dur,
        accepted=reason is None,
        reason=reason,
        min_knee_angle=min_angle,
        max_hip_drop=None,
        trunk_lean_at_bottom=trunk,
        knee_asymmetry_at_bottom=asym,
        invalid_ratio=0.0,
    )
