import pytest

from rep_engine.confidence import apply_calibration, compute_confidence
from rep_engine.config import EngineConfig
from rep_engine.schemas import (
    LivenessAction,
    LivenessEvidence,
    LivenessResult,
    LivenessStatus,
    RepReason,
)
from tests.featurize import make_rep, reps_for, skeletons
from tests.synth import SynthConfig, rep_windows, varied_squats

EV = LivenessEvidence(
    max_hold_ms=1000, wrong_hand_max_hold_ms=0, valid_frame_ratio=1.0, wrong_hand_detected=False
)


def lv(status: LivenessStatus, at: int | None = 0) -> LivenessResult:
    return LivenessResult(
        challenge_id="c",
        action=LivenessAction.RAISE_LEFT_HAND,
        status=status,
        passed_at_t=at if status is LivenessStatus.PASSED else None,
        evidence=EV,
    )


def conf(sc: SynthConfig, cfg: EngineConfig, liveness: LivenessResult | None):  # type: ignore[no-untyped-def]
    return compute_confidence(
        skeletons(sc), reps_for(sc, cfg), liveness, cfg.confidence, cfg.features.min_visibility
    )


def test_clean_session_is_high_and_in_range(cfg: EngineConfig) -> None:
    res = conf(
        SynthConfig(reps=varied_squats(10, seed=1), noise_px=1.0), cfg, lv(LivenessStatus.PASSED)
    )
    assert 0.9 <= res.ai_confidence <= 1.0
    c = res.components
    assert c.valid == 1.0 and c.track == 1.0 and c.unaccepted == 1.0 and c.vis == 0.9
    assert not c.liveness_penalty_applied


def test_more_invalid_frames_lower_confidence(cfg: EngineConfig) -> None:
    reps = varied_squats(8, seed=2)
    base = SynthConfig(reps=reps, noise_px=1.0)
    rests = [
        (e, s2)
        for (_, _, e), (s2, _, _) in zip(rep_windows(base), rep_windows(base)[1:], strict=False)
    ]
    values = []
    for k in (0, 2, 5):
        sc = SynthConfig(reps=reps, noise_px=1.0, invalid_ranges=rests[:k])
        values.append(conf(sc, cfg, lv(LivenessStatus.PASSED)).ai_confidence)
    assert values[0] > values[1] > values[2]


@pytest.mark.parametrize("status", [LivenessStatus.EXPIRED, LivenessStatus.FAILED_NO_PERSON, None])
def test_liveness_penalty(cfg: EngineConfig, status: LivenessStatus | None) -> None:
    sc = SynthConfig(reps=varied_squats(6, seed=3), noise_px=1.0)
    ok = conf(sc, cfg, lv(LivenessStatus.PASSED))
    bad = conf(sc, cfg, None if status is None else lv(status))
    assert bad.components.liveness_penalty_applied
    assert bad.components.raw == pytest.approx(
        ok.components.raw * cfg.confidence.liveness_penalty, abs=0.002
    )


def test_active_window_starts_at_liveness_pass(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=varied_squats(3, seed=4), invalid_ranges=[(0, 1500)])
    passed = conf(sc, cfg, lv(LivenessStatus.PASSED, at=1600))
    assert passed.components.active_start_t == 1600 and passed.components.valid == 1.0
    failed = conf(sc, cfg, lv(LivenessStatus.EXPIRED))
    assert failed.components.active_start_t == 0 and failed.components.valid < 1.0
    assert failed.components.track < 1.0


def test_calibration_mapping_applied(cfg: EngineConfig) -> None:
    pts = [(0.0, 0.0), (0.5, 0.2), (0.9, 0.5), (1.0, 1.0)]
    assert apply_calibration(0.7, pts) == pytest.approx(0.35)
    assert apply_calibration(1.2, pts) == 1.0 and apply_calibration(-1, pts) == 0.0
    new_cfg = cfg.confidence.model_copy(update={"calibration": pts})
    sc = SynthConfig(reps=varied_squats(5, seed=5), noise_px=1.0)
    res = compute_confidence(
        skeletons(sc),
        reps_for(sc, cfg),
        lv(LivenessStatus.PASSED),
        new_cfg,
        cfg.features.min_visibility,
    )
    assert res.ai_confidence == pytest.approx(apply_calibration(res.components.raw, pts), abs=0.002)


def test_neutral_scores_without_reps(cfg: EngineConfig) -> None:
    res = conf(SynthConfig(reps=[], lead_in_ms=3000), cfg, lv(LivenessStatus.PASSED))
    assert res.components.consistency == cfg.confidence.neutral_score
    assert res.components.unaccepted == cfg.confidence.neutral_score
    assert res.components.active_end_t is not None


def test_consistency_and_out_of_frame_components(cfg: EngineConfig) -> None:
    sk = skeletons(SynthConfig(reps=[], lead_in_ms=20000))
    even = [make_rep(i, i * 3000, 2000, 85.0) for i in range(1, 5)]
    uneven = [
        make_rep(i, i * 3000, d, a)
        for i, (d, a) in enumerate(
            [(1200, 60.0), (2800, 98.0), (1500, 70.0), (2600, 95.0)], start=1
        )
    ]
    c_even = compute_confidence(sk, even, None, cfg.confidence, 0.5).components
    c_uneven = compute_confidence(sk, uneven, None, cfg.confidence, 0.5).components
    assert c_even.consistency == 1.0 and c_uneven.consistency < c_even.consistency
    oof = [*even[:3], make_rep(4, 12000, reason=RepReason.OUT_OF_FRAME)]
    assert compute_confidence(sk, oof, None, cfg.confidence, 0.5).components.unaccepted == 0.75


def test_empty_frames(cfg: EngineConfig) -> None:
    res = compute_confidence([], [], None, cfg.confidence, 0.5)
    assert res.components.active_start_t is None and 0.0 <= res.ai_confidence <= 1.0
