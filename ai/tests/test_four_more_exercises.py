"""리버스 크런치·사이드 런지·버드독·카프 레이즈 판정 (D-89~D-93).

합성 데이터, 기준값은 cat_2026-11-24의 [가정] 값.

US-01 "가동범위 기준에 못 미친 렙은 미인정"을 종목만 바꿔 확인한다. 이 종목들은 MVP 범위
밖이며(mvp-scope.md) 엔진에만 있다.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from rep_engine.config import DEFAULT_CATALOG_DIR, Catalog, load_catalog, parse_catalog
from rep_engine.counters.base import make_counter, registered_exercises
from rep_engine.counters.bird_dog import BirdDogCounter
from rep_engine.counters.calf_raise import CalfRaiseCounter
from rep_engine.counters.reverse_crunch import ReverseCrunchCounter
from rep_engine.counters.side_lunge import SideLungeCounter
from rep_engine.errors import ConfigError, UnsupportedExerciseError
from rep_engine.schemas import (
    AnomalyCode,
    BirdDogPoseSummary,
    BirdDogRepEvent,
    CalfRaisePoseSummary,
    CalfRaiseRepEvent,
    FormTag,
    RepReason,
    ReverseCrunchPoseSummary,
    ReverseCrunchRepEvent,
    SessionResult,
    SideLungePoseSummary,
    SideLungeRepEvent,
)
from rep_engine.session import run_session
from service.app import TOKEN_ENV, app
from tools import synth, synth_floor, synth_more
from tools.synth_extra import ExtraExercise, ExtraRep, ExtraSynthConfig, rep_windows, synth_session

NEW = "cat_2026-11-24"
PREV = "cat_2026-11-23"
#: 종목별 판정 값 (인정되는 값, 가동범위 미달 값, 시도로도 안 치는 값).
#: 리버스 크런치: 엉덩이 내각 / 사이드 런지: 굽힌 무릎 내각 / 버드독: 180 − min(팔·다리 뻗음)
#: (15 = 165° 뻗음) / 카프 레이즈: 100 − 발목 높이% (93 = 7%, 각도 아님)
ANGLES: dict[ExtraExercise, tuple[float, float, float]] = {
    "REVERSE_CRUNCH": (40.0, 58.0, 72.0),
    "SIDE_LUNGE": (100.0, 130.0, 150.0),
    "BIRD_DOG": (15.0, 40.0, 60.0),
    "CALF_RAISE": (93.0, 96.8, 98.0),
}
EXERCISES: list[ExtraExercise] = ["REVERSE_CRUNCH", "SIDE_LUNGE", "BIRD_DOG", "CALF_RAISE"]
PAIRED: list[ExtraExercise] = ["SIDE_LUNGE", "BIRD_DOG"]
EVENT_TYPES = {
    "REVERSE_CRUNCH": ReverseCrunchRepEvent,
    "SIDE_LUNGE": SideLungeRepEvent,
    "BIRD_DOG": BirdDogRepEvent,
    "CALF_RAISE": CalfRaiseRepEvent,
}
SUMMARY_TYPES = {
    "REVERSE_CRUNCH": ReverseCrunchPoseSummary,
    "SIDE_LUNGE": SideLungePoseSummary,
    "BIRD_DOG": BirdDogPoseSummary,
    "CALF_RAISE": CalfRaisePoseSummary,
}
SECTIONS = {
    "REVERSE_CRUNCH": "reverse_crunch",
    "SIDE_LUNGE": "side_lunge",
    "BIRD_DOG": "bird_dog",
    "CALF_RAISE": "calf_raise",
}
#: 합성 곡선에서 덜 뻗은 버드독은 기준선을 넘는 시간이 짧아 TOO_FAST가 먼저 걸린다 → 동작을 길게
SHALLOW_KW: dict[str, dict[str, int]] = {"BIRD_DOG": {"leg_ms": 2400}}


@pytest.fixture(scope="module")
def new_catalog() -> Catalog:
    return load_catalog(NEW)


def reps(n: int, angle: float, **kw: Any) -> list[ExtraRep]:
    return [ExtraRep(left_angle=angle, **kw) for _ in range(n)]


def run(cfg: ExtraSynthConfig, catalog: Catalog) -> SessionResult:
    meta, chunks = synth_session(cfg)
    return run_session(meta, chunks, catalog)


def _catalog_data() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    return data


# --- 네 종목 공통 -------------------------------------------------------------


@pytest.mark.parametrize("model", ["mediapipe", "movenet"])
@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_normal_reps_are_counted(
    new_catalog: Catalog, exercise: ExtraExercise, model: synth.Model
) -> None:
    good = ANGLES[exercise][0]
    res = run(ExtraSynthConfig(exercise, reps(5, good), model=model, noise_px=1.0), new_catalog)
    assert res.recognized_reps == 5 and res.attempted_reps == 5
    for e in res.reps:
        assert e.accepted and e.reason is None
        assert abs(e.depth_angle - good) < 5.0
    assert all(isinstance(e, EVENT_TYPES[exercise]) for e in res.reps)
    assert isinstance(res.pose_summary, SUMMARY_TYPES[exercise])


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_models_and_mirroring_agree(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    good = ANGLES[exercise][0]
    base = run(ExtraSynthConfig(exercise, reps(4, good)), new_catalog)
    movenet = run(ExtraSynthConfig(exercise, reps(4, good), model="movenet"), new_catalog)
    mirrored = run(ExtraSynthConfig(exercise, reps(4, good), mirrored=True), new_catalog)
    assert base.recognized_reps == 4
    assert base.reps == movenet.reps == mirrored.reps


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_shallow_reps_not_accepted(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    kw = SHALLOW_KW.get(exercise, {})
    res = run(ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][1], **kw)), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)
    assert FormTag.SHALLOW_DEPTH_FREQUENT in res.pose_summary.form_tags


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_small_motion_is_not_an_attempt(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    res = run(ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][2])), new_catalog)
    assert res.attempted_reps == 0


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_too_fast(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    leg_ms = {"REVERSE_CRUNCH": 300, "SIDE_LUNGE": 400, "BIRD_DOG": 400, "CALF_RAISE": 200}
    cfg = ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][0], leg_ms=leg_ms[exercise]), fps=30)
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    assert all(e.reason is RepReason.TOO_FAST for e in res.reps)


@pytest.mark.parametrize("exercise", ["REVERSE_CRUNCH", "CALF_RAISE"])
def test_us01_four_out_of_frame(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    # 1.1초 끊김이 다음 렙까지 덮지 않게 렙을 2초로
    cfg = ExtraSynthConfig(exercise, reps(5, ANGLES[exercise][0], leg_ms=1000))
    _, mid, _ = rep_windows(cfg)[2]
    cfg.invalid_ranges = [(mid - 100, mid + 1100)]
    res = run(cfg, new_catalog)
    assert [e.reason for e in res.reps] == [None, None, RepReason.OUT_OF_FRAME, None, None]
    assert res.recognized_reps == 4


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_result_json_roundtrip(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    """종목별 렙·요약 모양이 JSON만으로 다시 구별된다 (백엔드가 같은 스키마로 읽을 수 있음)."""
    res = run(ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][0])), new_catalog)
    assert SessionResult.model_validate(res.to_dict()) == res


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_is_deterministic(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    cfg = ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][0]), noise_px=1.5, seed=7)
    assert run(cfg, new_catalog).to_json() == run(cfg, new_catalog).to_json()


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_older_catalog_rejects_four(exercise: ExtraExercise) -> None:
    meta, chunks = synth_session(
        ExtraSynthConfig(exercise, reps(2, ANGLES[exercise][0]), catalog_version=PREV)
    )
    with pytest.raises(UnsupportedExerciseError):
        run_session(meta, chunks, load_catalog(PREV))


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_four_config_order_checked(exercise: ExtraExercise) -> None:
    data = _catalog_data()
    section = data[SECTIONS[exercise]]
    section["depth_accept_angle"] = section["attempt_angle"] + 1
    with pytest.raises(ConfigError):
        parse_catalog(data)


def test_us01_four_counters_registered(new_catalog: Catalog) -> None:
    assert set(EXERCISES) <= set(registered_exercises())
    cfg = new_catalog.for_model("mediapipe")
    assert isinstance(make_counter("REVERSE_CRUNCH", cfg), ReverseCrunchCounter)
    assert isinstance(make_counter("SIDE_LUNGE", cfg), SideLungeCounter)
    assert isinstance(make_counter("BIRD_DOG", cfg), BirdDogCounter)
    assert isinstance(make_counter("CALF_RAISE", cfg), CalfRaiseCounter)


# --- 새 카탈로그가 기존 종목을 바꾸지 않음 -----------------------------------


def test_us01_new_catalog_keeps_existing_sections() -> None:
    """cat_2026-11-24는 cat_2026-11-23에 네 종목·자세 범위·카프 레이즈 이상 징후만 더했다."""
    prev = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{PREV}.yaml").read_text())
    new = _catalog_data()
    assert set(new) - set(prev) == set(SECTIONS.values())
    for key in prev:
        if key == "catalog_version":
            continue
        if key in ("posture", "anomaly_by_exercise"):
            assert {k: v for k, v in new[key].items() if k not in SECTIONS.values()} == prev[key]
            continue
        assert new[key] == prev[key], key
    assert set(new["posture"]) - set(prev["posture"]) == set(SECTIONS.values())
    assert set(new["anomaly_by_exercise"]) - set(prev["anomaly_by_exercise"]) == {"calf_raise"}


def test_us01_existing_exercises_same_on_new_catalog(new_catalog: Catalog) -> None:
    prev_cat = load_catalog(PREV)

    def same(prev_session: Any, new_session: Any) -> None:
        a = run_session(*prev_session, prev_cat)
        b = run_session(*new_session, new_catalog)
        assert a.model_copy(update={"catalog_version": NEW}) == b

    def sq(v: str) -> Any:
        return synth.synth_session(
            synth.SynthConfig(reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=v)
        )

    same(sq(PREV), sq(NEW))
    for ex, angle in (("PUSHUP", 75.0), ("SITUP", 110.0)):
        rs = synth_floor.reps(3, angle)
        same(
            synth_floor.synth_session(synth_floor.FloorSynthConfig(ex, rs, catalog_version=PREV)),  # type: ignore[arg-type]
            synth_floor.synth_session(synth_floor.FloorSynthConfig(ex, rs, catalog_version=NEW)),  # type: ignore[arg-type]
        )
    more = {
        "LUNGE": 88.0,
        "INVERTED_SHOULDER_PRESS": 80.0,
        "GLUTE_BRIDGE": 8.0,
        "SIDE_LEG_LIFT": 140.0,
    }
    for ex, angle in more.items():
        rs = synth_floor.reps(3, angle)
        same(
            synth_more.synth_session(synth_more.MoreSynthConfig(ex, rs, catalog_version=PREV)),  # type: ignore[arg-type]
            synth_more.synth_session(synth_more.MoreSynthConfig(ex, rs, catalog_version=NEW)),  # type: ignore[arg-type]
        )
    extra: dict[ExtraExercise, float] = {
        "HIGH_KNEE": 85.0,
        "MOUNTAIN_CLIMBER": 95.0,
        "SUPERMAN": 155.0,
        "DONKEY_KICK": 20.0,
    }
    for ex2, angle in extra.items():
        same(
            synth_session(ExtraSynthConfig(ex2, reps(3, angle), catalog_version=PREV)),
            synth_session(ExtraSynthConfig(ex2, reps(3, angle), catalog_version=NEW)),
        )


# --- 리버스 크런치 (D-89) ------------------------------------------------------


def test_us01_reverse_crunch_summary(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("REVERSE_CRUNCH", reps(4, 40.0)), new_catalog)
    s = res.pose_summary.to_dict()
    assert abs(s["hipCurlDeg"]["avg"] - 140.0) < 3.0
    assert s["torsoTiltDeg"]["avg"] >= 65


def _deep_situp() -> Any:
    """상체를 88° 일으키는 윗몸 일으키기, 렙 3초.

    엉덩이 내각이 약 48°라 리버스 크런치 기준(50° 이하)은 넘는다.
    """
    return synth_floor.synth_session(
        synth_floor.FloorSynthConfig(
            "SITUP", synth_floor.reps(5, 92.0, duration_ms=3000), catalog_version=NEW
        )
    )


def test_us01_situp_motion_not_counted_as_reverse_crunch(new_catalog: Catalog) -> None:
    """상체를 일으키는 윗몸 일으키기는 리버스 크런치로 세지 않는다 (상체 유지·자세 확인)."""
    meta, chunks = _deep_situp()
    res = run_session(
        meta.model_copy(update={"exercise_type": "REVERSE_CRUNCH"}), chunks, new_catalog
    )
    assert res.recognized_reps == 0


def test_us01_reverse_crunch_torso_rule_is_what_rejects_situp() -> None:
    """상체 유지 조건(과 자세 확인)을 끄면 윗몸 일으키기가 리버스 크런치로 세어진다.

    조건이 실제로 거르고 있는지 확인한다. 켜면 0회(위 테스트), 끄면 세어짐.
    """
    data = _catalog_data()
    data["reverse_crunch"]["min_torso_tilt"] = 1
    data["posture"]["reverse_crunch"] = {"min_deg": 0, "max_deg": 180}
    meta, chunks = _deep_situp()
    res = run_session(
        meta.model_copy(update={"exercise_type": "REVERSE_CRUNCH"}), chunks, parse_catalog(data)
    )
    assert res.recognized_reps > 0


# --- 사이드 런지·버드독: 두 쪽 = 1렙 (D-90, D-91) ------------------------------


@pytest.mark.parametrize("exercise", PAIRED)
def test_us01_paired_one_side_shallow_fails_the_pair(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    good, shallow, _ = ANGLES[exercise]
    kw = SHALLOW_KW.get(exercise, {})
    res = run(ExtraSynthConfig(exercise, reps(3, good, right_angle=shallow, **kw)), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 3
    for e in res.reps:
        d = e.to_dict()
        assert d["leftReason"] is None and d["rightReason"] == "SHALLOW_DEPTH"


@pytest.mark.parametrize("exercise", PAIRED)
def test_us01_paired_one_side_only_is_not_counted(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    cfg = ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][0]), legs="left_only")
    assert run(cfg, new_catalog).attempted_reps == 0


def test_us01_side_lunge_squat_is_not_counted(new_catalog: Catalog) -> None:
    """두 무릎을 같이 굽히면(스쿼트) 반대 다리가 펴져 있지 않아 미인정."""
    res = run(ExtraSynthConfig("SIDE_LUNGE", reps(4, 100.0), legs="both"), new_catalog)
    assert res.recognized_reps == 0
    assert res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, SideLungeRepEvent)
        assert e.min_other_knee_angle is not None and e.min_other_knee_angle < 160


def test_us01_side_lunge_without_stepping_out_is_not_counted(new_catalog: Catalog) -> None:
    """발을 옆으로 벌리지 않고 무릎만 꺾으면 다리 벌림이 작아 미인정."""
    res = run(ExtraSynthConfig("SIDE_LUNGE", reps(4, 100.0), stance="narrow"), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, SideLungeRepEvent)
        assert e.reason is RepReason.SHALLOW_DEPTH
        assert e.min_lateral_spread is not None and e.min_lateral_spread < 40


def test_us01_bird_dog_same_side_arm_and_leg_not_counted(new_catalog: Catalog) -> None:
    """같은 쪽 팔·다리(왼팔+왼다리)를 뻗으면 어느 쪽 판정 값도 작아지지 않는다."""
    res = run(ExtraSynthConfig("BIRD_DOG", reps(4, 15.0), legs="same_side"), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 0


def test_us01_superman_motion_not_counted_as_bird_dog(new_catalog: Catalog) -> None:
    """엎드려 양팔·다리를 드는 슈퍼맨은 받치는 팔이 없어 버드독으로 세지 않는다."""
    meta, chunks = synth_session(ExtraSynthConfig("SUPERMAN", reps(5, 150.0), catalog_version=NEW))
    res = run_session(meta.model_copy(update={"exercise_type": "BIRD_DOG"}), chunks, new_catalog)
    assert res.recognized_reps == 0


def test_us01_bird_dog_summary(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("BIRD_DOG", reps(4, 15.0)), new_catalog)
    s = res.pose_summary.to_dict()
    assert s["extensionDeg"]["min"] >= 150
    assert s["supportArmDeg"]["avg"] >= 130


# --- 카프 레이즈 (D-92) --------------------------------------------------------


def test_us01_calf_raise_jump_is_not_counted(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("CALF_RAISE", reps(4, 80.0)), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, CalfRaiseRepEvent)
        assert e.reason is RepReason.SHALLOW_DEPTH and e.max_ankle_lift_pct > 15


def test_us01_calf_raise_bent_knees_not_counted(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("CALF_RAISE", reps(4, 93.0), knee_bend=140.0), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)


def test_us01_calf_raise_summary_and_pace(new_catalog: Catalog) -> None:
    """빠른 카프 레이즈(1렙 약 0.9초)는 종목별 기준으로 UNREALISTIC_PACE가 아니다 (D-93)."""
    res = run(ExtraSynthConfig("CALF_RAISE", reps(6, 93.0)), new_catalog)
    s = res.pose_summary.to_dict()
    assert abs(s["ankleLiftPct"]["avg"] - 7.0) < 1.0
    assert s["kneeAngleDeg"]["avg"] > 170
    assert AnomalyCode.UNREALISTIC_PACE not in {a.code for a in res.anomalies}
    data = _catalog_data()
    del data["anomaly_by_exercise"]["calf_raise"]
    common = run(ExtraSynthConfig("CALF_RAISE", reps(6, 93.0)), parse_catalog(data))
    assert AnomalyCode.UNREALISTIC_PACE in {a.code for a in common.anomalies}


def test_us01_calf_raise_standing_still_is_not_a_rep(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("CALF_RAISE", [], noise_px=1.5, tail_ms=5000), new_catalog)
    assert res.attempted_reps == 0


# --- 자세 확인 (D-75): 고른 종목과 다른 자세로는 세지 않음 ------------------------


@pytest.mark.parametrize(
    ("motion", "declared"),
    [
        ("CALF_RAISE", "REVERSE_CRUNCH"),  # 서 있는 동작을 누운 종목으로
        ("BIRD_DOG", "SIDE_LUNGE"),  # 네발 자세를 서서 하는 종목으로
        ("SIDE_LUNGE", "BIRD_DOG"),
        ("REVERSE_CRUNCH", "CALF_RAISE"),
    ],
)
def test_us01_four_posture_wrong_exercise_is_not_counted(
    new_catalog: Catalog, motion: ExtraExercise, declared: str
) -> None:
    meta, chunks = synth_session(ExtraSynthConfig(motion, reps(5, ANGLES[motion][0])))
    res = run_session(meta.model_copy(update={"exercise_type": declared}), chunks, new_catalog)
    assert res.recognized_reps == 0


# --- 서버 재계산 API ----------------------------------------------------------


def test_us01_recount_api_four_exercises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    client = TestClient(app)
    expected_fields = {
        "REVERSE_CRUNCH": ({"minCrunchHipAngle", "minTorsoTilt"}, "hipCurlDeg"),
        "SIDE_LUNGE": ({"leftMinKneeAngle", "minLateralSpread"}, "lungeKneeBendDeg"),
        "BIRD_DOG": ({"leftSideExtension", "minSupportArmAngle"}, "extensionDeg"),
        "CALF_RAISE": ({"maxAnkleLiftPct", "minKneeAngleInRep"}, "ankleLiftPct"),
    }
    for exercise in EXERCISES:
        meta, chunks = synth_session(ExtraSynthConfig(exercise, reps(5, ANGLES[exercise][0])))
        body = {
            "meta": meta.to_dict(),
            "chunks": [c.to_dict() for c in chunks],
            "client": {"clientRepCount": 5, "reps": [], "aiConfidence": 0.9, "poseSummary": None},
        }
        r = client.post("/internal/recount", json=body, headers={"X-Internal-Token": "t"})
        assert r.status_code == 200, r.text
        res = r.json()["result"]
        assert res["recognizedReps"] == 5
        rep_fields, summary_field = expected_fields[exercise]
        assert rep_fields <= set(res["reps"][0])
        assert summary_field in res["poseSummary"]


# --- 웹캠 데모 (카메라·cv2 없이) ------------------------------------------------


@pytest.mark.parametrize("exercise", EXERCISES)
def test_demo_four_exercise_reaches_goal_of_5(exercise: ExtraExercise) -> None:
    """버튼(키)으로 고른 새 운동도 그 운동으로 판정하고, 인정 5회에서 목표 달성이 된다 (D-93)."""
    from tools.synth_extra import synth_frames
    from tools.webcam_demo import ALL_EXERCISES, DEMO_CATALOG, Demo, key_to_exercise

    assert exercise in ALL_EXERCISES
    assert any(key_to_exercise(k) == exercise for k in range(256))
    demo = Demo(720, 1280, "lite", "test", False, DEMO_CATALOG)
    assert demo.set_exercise(exercise, start_t=0)
    goal_seen_at: int | None = None
    for f in synth_frames(ExtraSynthConfig(exercise, reps(6, ANGLES[exercise][0]))):
        demo.push(f)
        if demo.goal_reached and goal_seen_at is None:
            goal_seen_at = demo.runner.counter.accepted_count
    assert goal_seen_at == 5
    assert len(demo.graph_lines()) == 3
