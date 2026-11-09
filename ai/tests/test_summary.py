import pytest

from rep_engine.config import EngineConfig
from rep_engine.schemas import FormTag, RepReason
from rep_engine.summary import pose_summary
from tests.featurize import make_rep, reps_for
from tests.synth import SynthConfig, varied_squats


def test_values(cfg: EngineConfig) -> None:
    reps = [
        make_rep(1, 0, 2000, 80.0, trunk=20.0, asym=2.0),
        make_rep(2, 3000, 2400, 90.0, trunk=30.0, asym=4.0),
        make_rep(3, 6000, 1000, 120.0, reason=RepReason.SHALLOW_DEPTH),
    ]
    s = pose_summary(reps, cfg.form_tags)
    assert s.knee_flexion_deg is not None
    assert (s.knee_flexion_deg.avg, s.knee_flexion_deg.min, s.knee_flexion_deg.max) == (
        95.0,
        90.0,
        100.0,
    )
    assert s.trunk_lean_deg is not None and (s.trunk_lean_deg.avg, s.trunk_lean_deg.max) == (
        25.0,
        30.0,
    )
    assert s.knee_asymmetry_deg is not None and s.knee_asymmetry_deg.avg == 3.0
    assert s.rep_duration_ms is not None
    assert (s.rep_duration_ms.avg, s.rep_duration_ms.std) == (2200.0, 200.0)
    assert s.depth_consistency_deg == 5.0
    assert s.form_tags == [FormTag.SHALLOW_DEPTH_FREQUENT]  # 1/3 > 0.3
    d = s.to_dict()
    assert set(d) == {
        "kneeFlexionDeg",
        "trunkLeanDeg",
        "kneeAsymmetryDeg",
        "repDurationMs",
        "depthConsistencyDeg",
        "formTags",
    }


def test_no_accepted_reps_gives_nulls(cfg: EngineConfig) -> None:
    s = pose_summary([make_rep(reason=RepReason.TOO_FAST)], cfg.form_tags)
    assert s.knee_flexion_deg is None and s.rep_duration_ms is None
    assert s.depth_consistency_deg is None
    assert s.form_tags == [FormTag.TEMPO_TOO_FAST]
    assert pose_summary([], cfg.form_tags).form_tags == []


def test_missing_trunk_and_asym(cfg: EngineConfig) -> None:
    s = pose_summary([make_rep(trunk=None, asym=None)], cfg.form_tags)
    assert s.trunk_lean_deg is None and s.knee_asymmetry_deg is None


@pytest.mark.parametrize(
    ("reps", "tag", "present"),
    [
        (
            [make_rep(1, min_angle=60.0), make_rep(2, min_angle=95.0)],
            FormTag.DEPTH_INCONSISTENT,
            True,
        ),
        (
            [make_rep(1, min_angle=80.0), make_rep(2, min_angle=95.0)],
            FormTag.DEPTH_INCONSISTENT,
            False,
        ),
        ([make_rep(trunk=50.0)], FormTag.TRUNK_LEAN_EXCESSIVE, True),
        ([make_rep(trunk=45.0)], FormTag.TRUNK_LEAN_EXCESSIVE, False),
        ([make_rep(asym=16.0)], FormTag.KNEE_ASYMMETRY, True),
        ([make_rep(asym=15.0)], FormTag.KNEE_ASYMMETRY, False),
        (
            [
                make_rep(1),
                make_rep(2),
                make_rep(3),
                make_rep(4),
                make_rep(5, reason=RepReason.TOO_FAST),
            ],
            FormTag.TEMPO_TOO_FAST,
            False,
        ),  # 0.2는 초과가 아님
        (
            [make_rep(1), make_rep(2), make_rep(3, reason=RepReason.OUT_OF_FRAME)],
            FormTag.FREQUENT_OUT_OF_FRAME,
            True,
        ),
        (
            [make_rep(1), make_rep(2), make_rep(3), make_rep(4, reason=RepReason.SHALLOW_DEPTH)],
            FormTag.SHALLOW_DEPTH_FREQUENT,
            False,
        ),  # 0.25
    ],
)
def test_form_tag_conditions(cfg: EngineConfig, reps, tag, present) -> None:  # type: ignore[no-untyped-def]
    assert (tag in pose_summary(reps, cfg.form_tags).form_tags) is present


def test_synthetic_session_summary(cfg: EngineConfig) -> None:
    reps = reps_for(SynthConfig(reps=varied_squats(6, seed=9), noise_px=1.0), cfg)
    s = pose_summary(reps, cfg.form_tags)
    assert s.knee_flexion_deg is not None and 85 <= s.knee_flexion_deg.avg <= 106
    assert s.form_tags == []
