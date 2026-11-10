"""푸시업·윗몸 일으키기 판정 (합성 데이터, 기준값은 cat_2026-11-10의 [가정] 값).

US-01 "가동범위 기준에 못 미친 렙은 미인정"을 종목만 바꿔 확인한다. 이 종목들은 MVP 범위
밖이며(mvp-scope.md) 엔진에만 있다 (DECISIONS D-66).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from rep_engine.config import DEFAULT_CATALOG_DIR, Catalog, load_catalog, parse_catalog
from rep_engine.counters.base import make_counter, registered_exercises
from rep_engine.counters.flexion import REST
from rep_engine.counters.pushup import PushupCounter
from rep_engine.counters.situp import SitupCounter
from rep_engine.errors import ConfigError, UnsupportedExerciseError
from rep_engine.features.chain import ChainFeatures
from rep_engine.schemas import (
    FormTag,
    PushupPoseSummary,
    PushupRepEvent,
    RepReason,
    SessionResult,
    SitupPoseSummary,
    SitupRepEvent,
)
from rep_engine.session import run_session
from service.app import TOKEN_ENV, app
from tools import synth
from tools.synth_floor import FloorExercise, FloorSynthConfig, rep_windows, reps, synth_session

NEW = "cat_2026-11-10"
OLD = "cat_2026-11-01"
#: 종목별 판정 각도 (인정되는 최저 각도, 가동범위 미달 각도, 시도로도 안 치는 각도).
#: 윗몸 일으키기는 상체 각도(어깨–엉덩이–발목): 110 = 상체 70° 들림, 135 = 45°, 170 = 10°
ANGLES: dict[FloorExercise, tuple[float, float, float]] = {
    "PUSHUP": (75.0, 110.0, 140.0),
    "SITUP": (110.0, 135.0, 170.0),
}
EXERCISES: list[FloorExercise] = ["PUSHUP", "SITUP"]


@pytest.fixture(scope="module")
def new_catalog() -> Catalog:
    return load_catalog(NEW)


def run(cfg: FloorSynthConfig, catalog: Catalog) -> SessionResult:
    meta, chunks = synth_session(cfg)
    return run_session(meta, chunks, catalog)


@pytest.mark.parametrize("model", ["mediapipe", "movenet"])
@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_normal_reps_are_counted(
    new_catalog: Catalog, exercise: FloorExercise, model: synth.Model
) -> None:
    good = ANGLES[exercise][0]
    res = run(FloorSynthConfig(exercise, reps(5, good), model=model, noise_px=1.0), new_catalog)
    assert res.recognized_reps == 5 and res.attempted_reps == 5
    for e in res.reps:
        assert e.accepted and e.reason is None
        assert abs(e.depth_angle - good) < 2.0
    event_type = PushupRepEvent if exercise == "PUSHUP" else SitupRepEvent
    summary_type = PushupPoseSummary if exercise == "PUSHUP" else SitupPoseSummary
    assert all(isinstance(e, event_type) for e in res.reps)
    assert isinstance(res.pose_summary, summary_type)


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_models_and_mirroring_agree(
    new_catalog: Catalog, exercise: FloorExercise
) -> None:
    good = ANGLES[exercise][0]
    base = run(FloorSynthConfig(exercise, reps(4, good)), new_catalog)
    movenet = run(FloorSynthConfig(exercise, reps(4, good), model="movenet"), new_catalog)
    mirrored = run(FloorSynthConfig(exercise, reps(4, good), mirrored=True), new_catalog)
    assert base.reps == movenet.reps == mirrored.reps


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_shallow_reps_not_accepted(
    new_catalog: Catalog, exercise: FloorExercise
) -> None:
    shallow = ANGLES[exercise][1]
    res = run(FloorSynthConfig(exercise, reps(4, shallow)), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)
    assert FormTag.SHALLOW_DEPTH_FREQUENT in res.pose_summary.form_tags


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_small_bend_is_not_an_attempt(
    new_catalog: Catalog, exercise: FloorExercise
) -> None:
    res = run(FloorSynthConfig(exercise, reps(3, ANGLES[exercise][2])), new_catalog)
    assert res.attempted_reps == 0


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_too_fast(new_catalog: Catalog, exercise: FloorExercise) -> None:
    res = run(
        FloorSynthConfig(exercise, reps(3, ANGLES[exercise][0], duration_ms=500)), new_catalog
    )
    assert res.recognized_reps == 0
    assert all(e.reason is RepReason.TOO_FAST for e in res.reps)


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_out_of_frame(new_catalog: Catalog, exercise: FloorExercise) -> None:
    cfg = FloorSynthConfig(exercise, reps(5, ANGLES[exercise][0]))
    _, bottom, _ = rep_windows(cfg)[2]
    cfg.invalid_ranges = [(bottom - 100, bottom + 1300)]
    res = run(cfg, new_catalog)
    assert [e.reason for e in res.reps] == [None, None, RepReason.OUT_OF_FRAME, None, None]
    assert res.recognized_reps == 4


def test_us01_pushup_body_line(new_catalog: Catalog) -> None:
    straight = run(FloorSynthConfig("PUSHUP", reps(4, 75)), new_catalog)
    sagging = run(FloorSynthConfig("PUSHUP", reps(4, 75), hip_sag=0.2), new_catalog)
    s0, s1 = straight.reps[0], sagging.reps[0]
    assert isinstance(s0, PushupRepEvent) and isinstance(s1, PushupRepEvent)
    assert s0.body_line_dev_at_bottom is not None and s0.body_line_dev_at_bottom < 1.0
    assert s1.body_line_dev_at_bottom is not None and s1.body_line_dev_at_bottom > 20.0
    assert FormTag.BODY_LINE_BROKEN not in straight.pose_summary.form_tags
    assert FormTag.BODY_LINE_BROKEN in sagging.pose_summary.form_tags
    # 엉덩이 처짐은 판정(팔꿈치)에는 영향이 없다
    assert sagging.recognized_reps == 4


def test_us01_situp_summary(new_catalog: Catalog) -> None:
    res = run(FloorSynthConfig("SITUP", reps(4, 110)), new_catalog)
    e = res.reps[0]
    assert isinstance(e, SitupRepEvent) and e.min_hip_angle is not None
    # 허벅지 45°, 상체 70° 들림 → 엉덩이 각도 = 180 − 45 − 70 = 65
    assert abs(e.min_hip_angle - 65.0) < 2.0
    assert e.knee_angle_at_bottom is not None and abs(e.knee_angle_at_bottom - 90.0) < 1.0
    ps = res.pose_summary
    assert isinstance(ps, SitupPoseSummary)
    assert ps.torso_raise_deg is not None and ps.hip_flexion_deg is not None
    assert abs(ps.torso_raise_deg.avg - (180.0 - e.min_torso_angle)) < 0.1
    assert abs(ps.hip_flexion_deg.avg - (180.0 - e.min_hip_angle)) < 0.1


def test_us01_situp_needs_hip_fold_too(new_catalog: Catalog) -> None:
    """다리를 거의 편 채(허벅지 10°) 상체만 65° 들면 상체 조건은 넘지만 엉덩이 조건을 못 넘는다."""
    res = run(FloorSynthConfig("SITUP", reps(4, 115), thigh_tilt_deg=10), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, SitupRepEvent) and e.min_hip_angle is not None
        assert e.min_torso_angle <= 120.0 and e.min_hip_angle > 80.0
        assert e.reason is RepReason.SHALLOW_DEPTH


def test_us01_situp_knee_pull_is_not_a_rep(new_catalog: Catalog) -> None:
    """무릎만 가슴 쪽으로 당기면 엉덩이 각도는 작아져도 상체가 안 올라와 인정되지 않는다."""
    only_knees = run(FloorSynthConfig("SITUP", reps(4, 170), thigh_raise_deg=55), new_catalog)
    assert only_knees.attempted_reps == 0
    half_up = run(FloorSynthConfig("SITUP", reps(4, 145), thigh_raise_deg=55), new_catalog)
    assert half_up.recognized_reps == 0 and half_up.attempted_reps == 4
    for e in half_up.reps:
        assert isinstance(e, SitupRepEvent) and e.min_hip_angle is not None
        assert e.min_hip_angle <= 80.0  # 엉덩이 조건만 보면 통과했을 렙
        assert e.reason is RepReason.SHALLOW_DEPTH


def test_us01_situp_hip_never_visible_is_out_of_frame(new_catalog: Catalog) -> None:
    """렙 동안 무릎이 한 번도 안 보여 엉덩이 각도를 못 재면 OUT_OF_FRAME (인정하지 않음)."""
    counter = SitupCounter.from_config(new_catalog.for_model("mediapipe"))
    angles = (
        [177.0] * 5 + [170.0 - 6.0 * i for i in range(11)] + [110.0 + 6.0 * i for i in range(12)]
    )
    feats = [
        ChainFeatures(t=i * 67, valid=True, angle=a, angle_raw=a, aux_angle=None)
        for i, a in enumerate(angles)
    ]
    events = counter.run(feats)
    assert counter.state == REST and len(events) == 1
    e = events[0]
    assert isinstance(e, SitupRepEvent) and e.min_hip_angle is None
    assert e.reason is RepReason.OUT_OF_FRAME


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_floor_result_json_roundtrip(new_catalog: Catalog, exercise: FloorExercise) -> None:
    """종목별 렙·요약 모양이 JSON만으로 다시 구별된다 (백엔드가 같은 스키마로 읽을 수 있음)."""
    res = run(FloorSynthConfig(exercise, reps(3, ANGLES[exercise][0])), new_catalog)
    assert SessionResult.model_validate(res.to_dict()) == res


def test_us01_squat_same_on_new_catalog(new_catalog: Catalog) -> None:
    """새 카탈로그에서도 스쿼트 판정은 옛 카탈로그와 같다 (스쿼트·공통 값이 같으므로)."""
    sc_old = synth.SynthConfig(reps=synth.varied_squats(5, seed=3), noise_px=1.5)
    sc_new = synth.SynthConfig(
        reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=NEW
    )
    old = run_session(*synth.synth_session(sc_old), load_catalog(OLD))
    new = run_session(*synth.synth_session(sc_new), new_catalog)
    assert old.model_copy(update={"catalog_version": NEW}) == new


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_old_catalog_rejects_floor_exercise(exercise: FloorExercise) -> None:
    cfg = FloorSynthConfig(exercise, reps(2, ANGLES[exercise][0]), catalog_version=OLD)
    with pytest.raises(UnsupportedExerciseError) as exc:
        run(cfg, load_catalog(OLD))
    assert exc.value.code == "VALIDATION_FAILED"


def test_us01_floor_counters_registered(new_catalog: Catalog) -> None:
    assert {"SQUAT", "PUSHUP", "SITUP"} <= set(registered_exercises())
    cfg = new_catalog.for_model("mediapipe")
    assert isinstance(make_counter("PUSHUP", cfg), PushupCounter)
    assert isinstance(make_counter("SITUP", cfg), SitupCounter)


@pytest.mark.parametrize("section", ["pushup", "situp"])
def test_us01_flexion_config_order_checked(section: str) -> None:
    data: dict[str, Any] = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    data[section]["attempt_angle"] = data[section]["flex_start_angle"] + 1  # 순서 어김
    with pytest.raises(ConfigError):
        parse_catalog(data)


def test_us01_recount_api_pushup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    meta, chunks = synth_session(FloorSynthConfig("PUSHUP", reps(5, 75)))
    body = {
        "meta": meta.to_dict(),
        "chunks": [c.to_dict() for c in chunks],
        "client": {"clientRepCount": 5, "reps": [], "aiConfidence": 0.9, "poseSummary": None},
    }
    r = TestClient(app).post("/internal/recount", json=body, headers={"X-Internal-Token": "t"})
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["recognizedReps"] == 5
    assert {"minElbowAngle", "bodyLineDevAtBottom", "elbowAsymmetryAtBottom"} <= set(res["reps"][0])
    assert "elbowFlexionDeg" in res["poseSummary"]


@pytest.mark.parametrize("rotation", [70.0, 90.0, -40.0])
def test_us01_pushup_arm_bends_off_the_floor_are_not_counted(
    new_catalog: Catalog, rotation: float
) -> None:
    """서 있거나 앉아서 팔만 굽혔다 펴면 렙으로 세지 않는다 (웹캠 실측에서 발견, D-71)."""
    cfg = FloorSynthConfig("PUSHUP", reps(4, 75), body_rotation_deg=rotation, noise_px=1.0)
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 0


def _pushup_feats(postures: list[float | None]) -> list[ChainFeatures]:
    """팔꿈치 170° → 75° → 170° 렙 1개. 프레임마다 자세 각도를 따로 준다."""
    angles = (
        [170.0] * 3 + [160.0 - 8.5 * i for i in range(11)] + [80.0 + 8.0 * i for i in range(12)]
    )
    assert len(postures) == len(angles)
    return [
        ChainFeatures(t=i * 67, valid=True, angle=a, angle_raw=a, posture_angle=p)
        for i, (a, p) in enumerate(zip(angles, postures, strict=True))
    ]


def test_us01_pushup_posture_rules(new_catalog: Catalog) -> None:
    cfg = new_catalog.for_model("mediapipe")
    n = 26
    lying = PushupCounter.from_config(cfg).run(_pushup_feats([10.0] * n))
    assert len(lying) == 1 and lying[0].accepted
    # 엉덩이가 안 보여 자세를 확인할 수 없으면 시작하지 않음
    unknown = PushupCounter.from_config(cfg).run(_pushup_feats([None] * n))
    assert unknown == []
    # 엎드려 시작했어도 최저점에서 자세가 무너지면(일어남) 기록하지 않음
    bottom_bad = [10.0] * 3 + [10.0] * 9 + [60.0] * 2 + [10.0] * 12
    assert PushupCounter.from_config(cfg).run(_pushup_feats(bottom_bad)) == []
