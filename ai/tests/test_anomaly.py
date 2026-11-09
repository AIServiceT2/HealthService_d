import math

from rep_engine.anomaly import detect_anomalies
from rep_engine.config import EngineConfig
from rep_engine.features.extractor import FeatureExtractor
from rep_engine.schemas import AnomalyCode, RepEvent, Severity
from tests.featurize import make_rep, reps_for, skeletons
from tools.synth import RepSpec, SynthConfig, rep_windows, varied_squats


def codes(
    sc: SynthConfig, cfg: EngineConfig, reps: list[RepEvent] | None = None
) -> set[AnomalyCode]:
    sks = skeletons(sc)
    ex = FeatureExtractor(cfg.features, cfg.squat.stand_angle)
    feats = [ex.update(s) for s in sks]
    r = reps_for(sc, cfg) if reps is None else reps
    diag = math.hypot(sc.image_width, sc.image_height)
    return {a.code for a in detect_anomalies(sks, feats, r, cfg, diag)}


def test_normal_session_has_no_anomalies(cfg: EngineConfig) -> None:
    assert codes(SynthConfig(reps=varied_squats(8, seed=1), noise_px=1.5, seed=1), cfg) == set()


def test_too_regular_timing(cfg: EngineConfig) -> None:
    reps = [make_rep(i, i * 3000, 2000) for i in range(1, 6)]
    sc = SynthConfig(reps=[], lead_in_ms=1000, noise_px=1.5)
    assert AnomalyCode.REP_TIMING_TOO_REGULAR in codes(sc, cfg, reps)
    assert AnomalyCode.REP_TIMING_TOO_REGULAR not in codes(sc, cfg, reps[:4])


def test_frozen_landmarks(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=varied_squats(3, seed=2), noise_px=1.5, frozen_ranges=[(3000, 5500)])
    found = codes(sc, cfg)
    assert AnomalyCode.LANDMARKS_FROZEN in found and AnomalyCode.ZERO_JITTER not in found
    short = SynthConfig(reps=varied_squats(3, seed=2), noise_px=1.5, frozen_ranges=[(3000, 4500)])
    assert AnomalyCode.LANDMARKS_FROZEN not in codes(short, cfg)


def test_zero_jitter(cfg: EngineConfig) -> None:
    # 잡음이 0.1px — 관절이 얼어붙지는 않았지만(움직임 > frozen 기준) 비현실적으로 매끈함
    sc = SynthConfig(reps=varied_squats(3, seed=3), noise_px=0.15, lead_in_ms=3000)
    found = codes(sc, cfg)
    assert AnomalyCode.ZERO_JITTER in found and AnomalyCode.LANDMARKS_FROZEN not in found


def test_body_proportion_shift(cfg: EngineConfig) -> None:
    reps = varied_squats(6, seed=4)
    base = SynthConfig(reps=reps, noise_px=1.5)
    mid = rep_windows(base)[3][0]
    sc = SynthConfig(reps=reps, noise_px=1.5, torso_scale_from=(mid, 1.4))
    assert AnomalyCode.BODY_PROPORTION_SHIFT in codes(sc, cfg)
    small = SynthConfig(reps=reps, noise_px=1.5, torso_scale_from=(mid, 1.1))
    assert AnomalyCode.BODY_PROPORTION_SHIFT not in codes(small, cfg)


def test_multiple_resets(cfg: EngineConfig) -> None:
    reps = varied_squats(5, seed=5)
    for r in reps:
        r.rest_ms = 1600
    sc = SynthConfig(reps=reps, noise_px=1.5)
    wins = rep_windows(sc)
    gaps = [(e + 100, e + 1300) for _, _, e in wins[:3]]
    sc.invalid_ranges = gaps
    assert AnomalyCode.MULTIPLE_RESETS in codes(sc, cfg)
    sc.invalid_ranges = gaps[:2]
    assert AnomalyCode.MULTIPLE_RESETS not in codes(sc, cfg)


def test_unrealistic_pace(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[], lead_in_ms=1000, noise_px=1.5)
    fast = [make_rep(i, i * 2000, 850 + 60 * i) for i in range(1, 4)]
    assert AnomalyCode.UNREALISTIC_PACE in codes(sc, cfg, fast)
    ok = [make_rep(i, i * 3000, 1500 + 60 * i) for i in range(1, 4)]
    assert AnomalyCode.UNREALISTIC_PACE not in codes(sc, cfg, ok)


def test_severities(cfg: EngineConfig) -> None:
    reps = [make_rep(i, i * 3000, 900) for i in range(1, 6)]
    sc = SynthConfig(reps=[RepSpec()], lead_in_ms=1000, noise_px=1.5)
    sks = skeletons(sc)
    ex = FeatureExtractor(cfg.features, cfg.squat.stand_angle)
    out = detect_anomalies(sks, [ex.update(s) for s in sks], reps, cfg, 1468.6)
    sev = {a.code: a.severity for a in out}
    assert sev[AnomalyCode.REP_TIMING_TOO_REGULAR] is Severity.HIGH
    assert sev[AnomalyCode.UNREALISTIC_PACE] is Severity.MEDIUM
    assert all(a.detail for a in out)


def test_empty_inputs(cfg: EngineConfig) -> None:
    assert detect_anomalies([], [], [], cfg, 100.0) == []
