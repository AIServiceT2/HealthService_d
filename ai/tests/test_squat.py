import random

import pytest

from rep_engine.config import Catalog, EngineConfig
from rep_engine.counters.base import make_counter, registered_exercises
from rep_engine.counters.squat import ASCENDING, DESCENDING, STANDING, SquatCounter
from rep_engine.schemas import RepEvent, RepReason
from tests.featurize import features
from tests.synth import STAND_ANGLE, RepSpec, SynthConfig, rep_windows, squats


def count(sc: SynthConfig, cfg: EngineConfig) -> list[RepEvent]:
    return SquatCounter(cfg.squat).run(features(sc, cfg))


def reasons(events: list[RepEvent]) -> list[RepReason | None]:
    return [e.reason for e in events]


def test_normal_ten_reps(cfg: EngineConfig) -> None:
    ev = count(SynthConfig(reps=squats(10)), cfg)
    assert len(ev) == 10 and all(e.accepted for e in ev)
    assert [e.index for e in ev] == list(range(1, 11))
    for e in ev:
        assert e.start_t < e.bottom_t < e.end_t
        assert e.min_knee_angle < cfg.squat.depth_accept_angle
        assert e.invalid_ratio == 0.0


def test_shallow_reps(cfg: EngineConfig) -> None:
    ev = count(SynthConfig(reps=squats(5, bottom_angle=120)), cfg)
    assert reasons(ev) == [RepReason.SHALLOW_DEPTH] * 5
    assert not any(e.accepted for e in ev)


def test_movement_above_attempt_angle_is_ignored(cfg: EngineConfig) -> None:
    assert count(SynthConfig(reps=squats(4, bottom_angle=150)), cfg) == []


def test_too_fast(cfg: EngineConfig) -> None:
    ev = count(SynthConfig(reps=squats(3, duration_ms=500, rest_ms=800)), cfg)
    assert reasons(ev) == [RepReason.TOO_FAST] * 3


def test_too_fast_descent_only(cfg: EngineConfig) -> None:
    # 전체 렙은 충분히 길지만 하강이 너무 짧음 (300ms 미만)
    ev = count(SynthConfig(reps=squats(2, duration_ms=2000, descent_frac=0.1)), cfg)
    assert reasons(ev) == [RepReason.TOO_FAST] * 2


def test_gap_in_rep_is_out_of_frame(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[RepSpec(duration_ms=4000)])
    start, _, _ = rep_windows(sc)[0]
    sc.invalid_ranges = [(start + 1000, start + 2500)]
    ev = count(sc, cfg)
    assert reasons(ev) == [RepReason.OUT_OF_FRAME]
    assert ev[0].end_t < start + 1000 + 100  # 마지막 유효 프레임에서 끊김


def test_invalid_ratio_out_of_frame(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[RepSpec(duration_ms=3000)])
    start, _, _ = rep_windows(sc)[0]
    sc.invalid_ranges = [(start + 600, start + 1300), (start + 1700, start + 2300)]
    ev = count(sc, cfg)
    assert reasons(ev) == [RepReason.OUT_OF_FRAME]
    assert ev[0].invalid_ratio > cfg.squat.max_invalid_ratio_in_rep


def test_reason_priority_out_of_frame_first(cfg: EngineConfig) -> None:
    # 얕고(120°) 빠르고(700ms) 가려진 렙 → OUT_OF_FRAME
    sc = SynthConfig(reps=[RepSpec(bottom_angle=120, duration_ms=700)])
    # 렙이 실제로 시작(하강 감지)된 프레임 바로 뒤부터 가린다
    rep_start = next(
        f.t
        for f in features(sc, cfg)
        if f.knee_angle is not None and f.knee_angle < cfg.squat.descent_start_angle
    )
    sc.invalid_ranges = [(rep_start + 1, rep_start + 250)]
    ev = count(sc, cfg)
    assert reasons(ev) == [RepReason.OUT_OF_FRAME]


def test_reason_priority_too_fast_over_shallow(cfg: EngineConfig) -> None:
    ev = count(SynthConfig(reps=[RepSpec(bottom_angle=120, duration_ms=600)]), cfg)
    assert reasons(ev) == [RepReason.TOO_FAST]


def _noisy(base: SynthConfig, amp: float, seed: int) -> SynthConfig:
    from tests.synth import knee_angle_at, total_ms

    def fn(t: int) -> float:
        return knee_angle_at(base, t) + random.Random(seed * 100003 + t).uniform(-amp, amp)

    return SynthConfig(angle_fn=fn, duration_ms=total_ms(base))


@pytest.mark.parametrize("seed", range(5))
def test_boundary_noise_no_double_count(cfg: EngineConfig, seed: int) -> None:
    # 바닥이 깊이 기준(100°) 근처, 서는 높이가 stand_angle(160°) 근처, ±5° 잡음
    base = SynthConfig(reps=squats(4, bottom_angle=100))
    ev = count(_noisy(base, 5.0, seed), cfg)
    assert len(ev) == 4

    def near_stand(t: int) -> float:
        return 163.0 + random.Random(seed + t).uniform(-5, 5)

    assert count(SynthConfig(angle_fn=near_stand, duration_ms=8000), cfg) == []


def _piecewise(pts: list[tuple[int, float]]) -> SynthConfig:
    def fn(t: int) -> float:
        for (t0, a0), (t1, a1) in zip(pts, pts[1:], strict=False):
            if t0 <= t <= t1:
                return a0 + (a1 - a0) * (t - t0) / (t1 - t0)
        return STAND_ANGLE

    return SynthConfig(angle_fn=fn, duration_ms=pts[-1][0])


@pytest.mark.parametrize(
    ("second_bottom", "bottom_window"),
    [
        (95.0, (3000, 3300)),  # 재하강했지만 최저값 갱신 없음 → ASCENDING 유지
        (80.0, (4200, 4500)),  # 재하강해 최저값 갱신 → DESCENDING 복귀, 최저 시각 갱신
    ],
)
def test_redescent_during_ascent_is_one_rep(
    cfg: EngineConfig, second_bottom: float, bottom_window: tuple[int, int]
) -> None:
    sc = _piecewise(
        [
            (0, STAND_ANGLE),
            (2000, STAND_ANGLE),
            (3000, 90.0),
            (3600, 130.0),
            (4200, second_bottom),
            (5400, STAND_ANGLE),
            (7000, STAND_ANGLE),
        ]
    )
    ev = count(sc, cfg)
    assert len(ev) == 1 and ev[0].accepted
    assert bottom_window[0] <= ev[0].bottom_t <= bottom_window[1]


def test_max_rep_ms_discards(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[RepSpec(duration_ms=16000), RepSpec()])
    ev = count(sc, cfg)
    assert len(ev) == 1 and ev[0].accepted and ev[0].index == 1
    assert ev[0].start_t >= rep_windows(sc)[1][0]


def test_gap_before_attempt_angle_is_not_recorded(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[RepSpec(duration_ms=4000)])
    start, _, _ = rep_windows(sc)[0]
    sc.invalid_ranges = [(start + 350, start + 3800)]
    assert count(sc, cfg) == []


def test_rep_in_progress_at_end_is_not_recorded(cfg: EngineConfig) -> None:
    # 두 번째 렙의 최저점 직후 세션이 끝남 → 첫 렙만 기록
    sc = _piecewise(
        [
            (0, STAND_ANGLE),
            (2000, STAND_ANGLE),
            (3000, 85.0),
            (4000, STAND_ANGLE),
            (5000, STAND_ANGLE),
            (6000, 85.0),
            (6300, 110.0),
        ]
    )
    ev = count(sc, cfg)
    assert len(ev) == 1 and ev[0].end_t < 5000


def test_fps_invariance(cfg: EngineConfig) -> None:
    reps = [
        RepSpec(duration_ms=d, bottom_angle=a)
        for d, a in [(2000, 80), (1600, 95), (2400, 120), (500, 85), (1800, 70)]
    ]
    e15 = count(SynthConfig(reps=reps, fps=15), cfg)
    e30 = count(SynthConfig(reps=reps, fps=30), cfg)
    assert reasons(e15) == reasons(e30)
    assert len(e15) == 5
    frame_ms = 1000 / 15
    for a, b in zip(e15, e30, strict=True):
        assert abs(a.start_t - b.start_t) <= frame_ms
        assert abs(a.bottom_t - b.bottom_t) <= frame_ms
        assert abs(a.end_t - b.end_t) <= frame_ms


def test_deterministic_bytes(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=squats(6, bottom_angle=95), noise_px=2.0, seed=7)
    j1 = "".join(e.to_json() for e in count(sc, cfg))
    j2 = "".join(e.to_json() for e in count(sc, cfg))
    assert j1 == j2 and j1


def test_streaming_equals_batch(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=squats(5, bottom_angle=95) + squats(2, bottom_angle=125), noise_px=3.0)
    feats = features(sc, cfg)
    batch = SquatCounter(cfg.squat).run(feats)
    stream_counter = SquatCounter(cfg.squat)
    stream: list[RepEvent] = []
    seen_states: set[str] = set()
    for f in feats:
        stream.extend(stream_counter.update(f))
        seen_states.add(stream_counter.state)
        assert stream_counter.accepted_count == sum(e.accepted for e in stream)
    assert stream == batch
    assert {STANDING, DESCENDING, ASCENDING} <= seen_states
    assert stream_counter.current_angle is not None


def test_front_view_hip_drop_mode(cfg: EngineConfig) -> None:
    sc = SynthConfig(view="front", reps=squats(4, bottom_angle=80))
    angle_only = count(sc, cfg)
    assert reasons(angle_only) == [RepReason.SHALLOW_DEPTH] * 4
    hip_cfg = cfg.model_copy(
        update={"squat": cfg.squat.model_copy(update={"depth_mode": "angle_or_hip_drop"})}
    )
    ev = count(sc, hip_cfg)
    assert all(e.accepted for e in ev) and len(ev) == 4
    assert all(e.max_hip_drop is not None and e.max_hip_drop >= 0.25 for e in ev)


def test_mirrored_flag_gives_same_result(cfg: EngineConfig) -> None:
    kw = {"reps": squats(4, bottom_angle=90) + squats(2, bottom_angle=125), "noise_px": 1.5}
    plain = count(SynthConfig(**kw), cfg)  # type: ignore[arg-type]
    mirrored = count(SynthConfig(mirrored=True, **kw), cfg)  # type: ignore[arg-type]
    assert plain == mirrored


def test_both_adapters_same_judgement(catalog: Catalog) -> None:
    reps = squats(3) + squats(2, bottom_angle=125) + squats(1, duration_ms=500)
    out = {}
    for model in ("mediapipe", "movenet"):
        sc = SynthConfig(reps=reps, model=model, noise_px=1.0, seed=3)  # type: ignore[arg-type]
        out[model] = count(sc, catalog.for_model(model))
    assert out["mediapipe"] == out["movenet"]
    assert reasons(out["movenet"]) == [None] * 3 + [RepReason.SHALLOW_DEPTH] * 2 + [
        RepReason.TOO_FAST
    ]


def test_registry(cfg: EngineConfig) -> None:
    assert "SQUAT" in registered_exercises()
    assert isinstance(make_counter("SQUAT", cfg), SquatCounter)
    with pytest.raises(KeyError):
        make_counter("PUSHUP", cfg)
