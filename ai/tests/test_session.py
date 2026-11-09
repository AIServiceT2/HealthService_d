import sys
import time
from pathlib import Path

import pytest

from rep_engine.config import Catalog
from rep_engine.errors import (
    CatalogNotFoundError,
    ConfigError,
    MissingChunksError,
    UnknownModelError,
)
from rep_engine.schemas import LivenessAction, LivenessStatus, SessionResult
from rep_engine.session import SessionRunner, run_frames, run_session
from tests.synth import SynthConfig, challenge, squats, synth_frames, synth_session, varied_squats

LEAD = 4000  # 무작위 동작 구간 뒤에 첫 렙이 시작되도록


def live_cfg(raise_hand: bool = True, **kw: object) -> SynthConfig:
    return SynthConfig(
        reps=kw.pop("reps", varied_squats(10, seed=11)),  # type: ignore[arg-type]
        lead_in_ms=LEAD,
        noise_px=1.5,
        hand_raises=[(500, 2000, "LEFT")] if raise_hand else [],
        liveness=challenge(LivenessAction.RAISE_LEFT_HAND, 0, 3000),
        **kw,  # type: ignore[arg-type]
    )


def test_full_session_auto_quality(catalog: Catalog) -> None:
    meta, chunks = synth_session(live_cfg())
    res = run_session(meta, chunks, catalog)
    assert res.recognized_reps == 10 and res.attempted_reps == 10
    assert res.liveness is not None and res.liveness.status is LivenessStatus.PASSED
    assert res.ai_confidence >= 0.9
    assert res.anomalies == []
    assert res.catalog_version == "cat_2026-11-01"
    d = res.to_dict()
    assert {
        "engineVersion",
        "recognizedReps",
        "aiConfidence",
        "confidenceComponents",
        "poseSummary",
    } <= set(d)


def test_loads_catalog_by_version(tmp_path: Path) -> None:
    meta, chunks = synth_session(live_cfg(reps=squats(1)))
    assert run_session(meta, chunks).recognized_reps == 1
    with pytest.raises(CatalogNotFoundError):
        run_session(meta, chunks, catalog_dir=tmp_path)


def test_deterministic_bytes(catalog: Catalog) -> None:
    meta, chunks = synth_session(live_cfg())
    assert (
        run_session(meta, chunks, catalog).to_json() == run_session(meta, chunks, catalog).to_json()
    )


def test_streaming_equals_batch(catalog: Catalog) -> None:
    sc = live_cfg()
    meta, chunks = synth_session(sc)
    runner = SessionRunner(meta, catalog)
    live = 0
    for f in synth_frames(sc):
        live += sum(e.accepted for e in runner.push(f))
        assert runner.counter.accepted_count == live
    assert runner.finish() == run_session(meta, chunks, catalog)
    assert runner.counting and runner.liveness_result is not None
    assert runner.last_features is not None


def test_reps_during_liveness_window_are_not_counted(catalog: Catalog) -> None:
    sc = live_cfg(reps=squats(3))
    sc.lead_in_ms = 500  # 첫 렙이 무작위 동작 확인 중(통과 전)에 시작됨
    sc.hand_raises = [(4000, 5500, "LEFT")]
    sc.liveness = challenge(LivenessAction.RAISE_LEFT_HAND, 0, 8000)
    meta, chunks = synth_session(sc)
    res = run_session(meta, chunks, catalog)
    assert res.liveness is not None and res.liveness.passed_at_t is not None
    assert all(e.start_t > res.liveness.passed_at_t for e in res.reps)
    assert res.recognized_reps < 3


def test_failed_liveness_counts_after_expiry_with_penalty(catalog: Catalog) -> None:
    meta, chunks = synth_session(live_cfg(raise_hand=False))
    res = run_session(meta, chunks, catalog)
    assert res.liveness is not None and res.liveness.status is LivenessStatus.EXPIRED
    assert res.recognized_reps == 10
    assert all(e.start_t > 3000 for e in res.reps)
    assert res.confidence_components.liveness_penalty_applied and res.ai_confidence < 0.6


def test_session_ending_before_liveness_resolves(catalog: Catalog) -> None:
    sc = live_cfg(raise_hand=False, reps=[])
    sc.lead_in_ms, sc.tail_ms = 1000, 0
    meta, chunks = synth_session(sc)
    res = run_session(meta, chunks, catalog)
    assert res.liveness is not None and res.liveness.status is LivenessStatus.EXPIRED
    assert res.reps == []


def test_no_liveness_counts_from_start(catalog: Catalog) -> None:
    sc = SynthConfig(reps=varied_squats(4, seed=2), noise_px=1.5)
    meta, chunks = synth_session(sc)
    res = run_session(meta, chunks, catalog)
    assert res.liveness is None and res.recognized_reps == 4
    assert res == run_frames(meta, synth_frames(sc), catalog)


def test_models_and_mirroring_give_same_result(catalog: Catalog) -> None:
    results = []
    for model in ("mediapipe", "movenet"):
        for mirrored in (False, True):
            meta, chunks = synth_session(live_cfg(model=model, mirrored=mirrored))
            results.append(run_session(meta, chunks, catalog))
    assert all(r == results[0] for r in results[1:])


def test_validation_errors(catalog: Catalog) -> None:
    meta, chunks = synth_session(live_cfg(reps=squats(2)), frames_per_chunk=40)
    assert len(chunks) >= 3
    with pytest.raises(MissingChunksError) as ei:
        run_session(meta, [chunks[0], *chunks[2:]], catalog)
    assert ei.value.missing_seq == [1]
    bad = meta.model_copy(update={"device": meta.device.model_copy(update={"model_version": "x"})})
    with pytest.raises(UnknownModelError):
        run_session(bad, chunks, catalog)
    other = meta.model_copy(update={"catalog_version": "cat_other"})
    with pytest.raises(ConfigError):
        run_session(other, chunks, catalog)


def test_performance_ten_minute_session(catalog: Catalog) -> None:
    """10분 세션(15fps, 9000프레임 이상) 재계산 < 1초 (SPEC 9.4).

    커버리지 계측(sys.settrace)은 실행을 2배 넘게 느리게 하므로, 실제 서버 실행 시간을 재도록
    측정 구간에서만 추적기를 잠시 끈다. 판정 결과 검사는 계측이 켜진 상태에서도 한다.
    """
    meta, chunks = synth_session(SynthConfig(reps=varied_squats(200, seed=1), noise_px=1.5))
    assert sum(len(c.frames) for c in chunks) >= 9000
    traced: SessionResult = run_session(meta, chunks, catalog)
    tracer = sys.gettrace()
    sys.settrace(None)
    try:
        t0 = time.perf_counter()
        res: SessionResult = run_session(meta, chunks, catalog)
        elapsed = time.perf_counter() - t0
    finally:
        sys.settrace(tracer)
    assert elapsed < 1.0, f"{elapsed:.3f}s"
    assert res == traced and res.recognized_reps == 200
