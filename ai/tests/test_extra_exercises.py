"""하이 니·마운틴 클라이머·슈퍼맨·돈키 킥 판정 (D-83~D-87).

합성 데이터, 기준값은 cat_2026-11-23의 [가정] 값.

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
from rep_engine.counters.donkey_kick import DonkeyKickCounter
from rep_engine.counters.high_knee import HighKneeCounter
from rep_engine.counters.mountain_climber import MountainClimberCounter
from rep_engine.counters.superman import SupermanCounter
from rep_engine.errors import ConfigError, UnsupportedExerciseError
from rep_engine.schemas import (
    AnomalyCode,
    Chunk,
    DonkeyKickPoseSummary,
    DonkeyKickRepEvent,
    FormTag,
    HighKneePoseSummary,
    HighKneeRepEvent,
    Landmark,
    MountainClimberPoseSummary,
    MountainClimberRepEvent,
    RepReason,
    SessionMeta,
    SessionResult,
    SupermanPoseSummary,
    SupermanRepEvent,
)
from rep_engine.session import run_session
from service.app import TOKEN_ENV, app
from tools import synth, synth_floor, synth_more
from tools.synth_extra import ExtraExercise, ExtraRep, ExtraSynthConfig, rep_windows, synth_session

NEW = "cat_2026-11-23"
PREV = "cat_2026-11-17"
#: 종목별 판정 각도 (인정되는 최저 각도, 가동범위 미달 각도, 시도로도 안 치는 각도).
#: 하이 니·마운틴 클라이머는 다리별 엉덩이 내각, 슈퍼맨은 몸 활 각도(어깨–엉덩이–발목),
#: 돈키 킥은 180 − 찬 다리 엉덩이 내각 (20 = 내각 160°, 45 = 135°, 62 = 118°)
ANGLES: dict[ExtraExercise, tuple[float, float, float]] = {
    "HIGH_KNEE": (85.0, 115.0, 140.0),
    "MOUNTAIN_CLIMBER": (95.0, 120.0, 145.0),
    "SUPERMAN": (155.0, 165.0, 171.0),
    "DONKEY_KICK": (20.0, 45.0, 62.0),
}
EXERCISES: list[ExtraExercise] = ["HIGH_KNEE", "MOUNTAIN_CLIMBER", "SUPERMAN", "DONKEY_KICK"]
ALTERNATING: list[ExtraExercise] = ["HIGH_KNEE", "MOUNTAIN_CLIMBER"]
EVENT_TYPES = {
    "HIGH_KNEE": HighKneeRepEvent,
    "MOUNTAIN_CLIMBER": MountainClimberRepEvent,
    "SUPERMAN": SupermanRepEvent,
    "DONKEY_KICK": DonkeyKickRepEvent,
}
SUMMARY_TYPES = {
    "HIGH_KNEE": HighKneePoseSummary,
    "MOUNTAIN_CLIMBER": MountainClimberPoseSummary,
    "SUPERMAN": SupermanPoseSummary,
    "DONKEY_KICK": DonkeyKickPoseSummary,
}
SECTIONS = {
    "HIGH_KNEE": "high_knee",
    "MOUNTAIN_CLIMBER": "mountain_climber",
    "SUPERMAN": "superman",
    "DONKEY_KICK": "donkey_kick",
}
#: 기존 7종목 (새 카탈로그에서도 결과가 같아야 함)
OLD_MORE = ["LUNGE", "INVERTED_SHOULDER_PRESS", "GLUTE_BRIDGE", "SIDE_LEG_LIFT"]
OLD_MORE_ANGLE = {
    "LUNGE": 88.0,
    "INVERTED_SHOULDER_PRESS": 80.0,
    "GLUTE_BRIDGE": 8.0,
    "SIDE_LEG_LIFT": 140.0,
}


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


def _rotate_90(meta: SessionMeta, chunks: list[Chunk]) -> tuple[SessionMeta, list[Chunk]]:
    """세션 전체를 시계 방향으로 90° 돌린다 (서 있던 사람이 누운 것처럼 보임)."""

    def rot(lm: Landmark | None) -> Landmark | None:
        return None if lm is None else lm.model_copy(update={"x": 1.0 - lm.y, "y": lm.x})

    new_chunks = [
        c.model_copy(
            update={
                "frames": [
                    f
                    if f.landmarks is None
                    else f.model_copy(update={"landmarks": [rot(lm) for lm in f.landmarks]})
                    for f in c.frames
                ]
            }
        )
        for c in chunks
    ]
    new_meta = meta.model_copy(
        update={"image_width": meta.image_height, "image_height": meta.image_width}
    )
    return new_meta, new_chunks


# --- 네 종목 공통 -------------------------------------------------------------


@pytest.mark.parametrize("model", ["mediapipe", "movenet"])
@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_normal_reps_are_counted(
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
def test_us01_extra_models_and_mirroring_agree(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    """MoveNet·미러링(어댑터가 원래대로 되돌림, D-03)이어도 결과가 같다."""
    good = ANGLES[exercise][0]
    base = run(ExtraSynthConfig(exercise, reps(4, good)), new_catalog)
    movenet = run(ExtraSynthConfig(exercise, reps(4, good), model="movenet"), new_catalog)
    mirrored = run(ExtraSynthConfig(exercise, reps(4, good), mirrored=True), new_catalog)
    assert base.recognized_reps == 4
    assert base.reps == movenet.reps == mirrored.reps


def test_us01_donkey_kick_either_leg(new_catalog: Catalog) -> None:
    """오른다리로 차도 센다. 좌우를 바꾼 화면(미러링 좌표를 mirrored=false로 보냄)으로 만든다."""
    meta, chunks = synth_session(ExtraSynthConfig("DONKEY_KICK", reps(4, 20.0), mirrored=True))
    res = run_session(meta.model_copy(update={"mirrored": False}), chunks, new_catalog)
    assert res.recognized_reps == 4


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_shallow_reps_not_accepted(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    res = run(ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][1])), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)
    assert FormTag.SHALLOW_DEPTH_FREQUENT in res.pose_summary.form_tags


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_small_motion_is_not_an_attempt(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    res = run(ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][2])), new_catalog)
    assert res.attempted_reps == 0


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_too_fast(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    # 번갈아 하는 종목: 다리 하나 0.18초 (기준 0.15초보다 판정 구간이 짧음). 30fps로 최저점을 잡는다
    leg_ms, fps = (180, 30) if exercise in ALTERNATING else (300, 15)
    cfg = ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][0], leg_ms=leg_ms), fps=fps)
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    assert all(e.reason is RepReason.TOO_FAST for e in res.reps)


@pytest.mark.parametrize("exercise", ["SUPERMAN", "DONKEY_KICK"])
def test_us01_extra_out_of_frame(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    cfg = ExtraSynthConfig(exercise, reps(5, ANGLES[exercise][0]))
    _, mid, _ = rep_windows(cfg)[2]
    cfg.invalid_ranges = [(mid - 100, mid + 1300)]
    res = run(cfg, new_catalog)
    assert [e.reason for e in res.reps] == [None, None, RepReason.OUT_OF_FRAME, None, None]
    assert res.recognized_reps == 4


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_result_json_roundtrip(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    """종목별 렙·요약 모양이 JSON만으로 다시 구별된다 (백엔드가 같은 스키마로 읽을 수 있음)."""
    res = run(ExtraSynthConfig(exercise, reps(3, ANGLES[exercise][0])), new_catalog)
    assert SessionResult.model_validate(res.to_dict()) == res


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_is_deterministic(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    cfg = ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][0]), noise_px=1.5, seed=7)
    assert run(cfg, new_catalog).to_json() == run(cfg, new_catalog).to_json()


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_older_catalog_rejects_extra_exercises(exercise: ExtraExercise) -> None:
    meta, chunks = synth_session(
        ExtraSynthConfig(exercise, reps(2, ANGLES[exercise][0]), catalog_version=PREV)
    )
    with pytest.raises(UnsupportedExerciseError):
        run_session(meta, chunks, load_catalog(PREV))


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_extra_config_order_checked(exercise: ExtraExercise) -> None:
    data = _catalog_data()
    section = data[SECTIONS[exercise]]
    section["depth_accept_angle"] = section["attempt_angle"] + 1
    with pytest.raises(ConfigError):
        parse_catalog(data)


def test_us01_extra_counters_registered(new_catalog: Catalog) -> None:
    assert set(EXERCISES) <= set(registered_exercises())
    cfg = new_catalog.for_model("mediapipe")
    assert isinstance(make_counter("HIGH_KNEE", cfg), HighKneeCounter)
    assert isinstance(make_counter("MOUNTAIN_CLIMBER", cfg), MountainClimberCounter)
    assert isinstance(make_counter("SUPERMAN", cfg), SupermanCounter)
    assert isinstance(make_counter("DONKEY_KICK", cfg), DonkeyKickCounter)


# --- 새 카탈로그가 기존 종목을 바꾸지 않음 -----------------------------------


def test_us01_new_catalog_keeps_existing_sections() -> None:
    """cat_2026-11-23은 cat_2026-11-17에 네 종목·자세 범위·종목별 이상 징후만 더했다."""
    prev = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{PREV}.yaml").read_text())
    new = _catalog_data()
    added = set(new) - set(prev)
    assert added == {*SECTIONS.values(), "anomaly_by_exercise"}
    for key in prev:
        if key == "catalog_version":
            continue
        if key == "posture":
            assert {k: v for k, v in new[key].items() if k not in SECTIONS.values()} == prev[key]
            assert set(new[key]) - set(prev[key]) == set(SECTIONS.values())
            continue
        assert new[key] == prev[key], key
    assert set(new["anomaly_by_exercise"]) == {"high_knee", "mountain_climber"}


def test_us01_existing_exercises_same_on_new_catalog(new_catalog: Catalog) -> None:
    prev_cat = load_catalog(PREV)

    def same(meta_chunks_prev: Any, meta_chunks_new: Any) -> None:
        a = run_session(*meta_chunks_prev, prev_cat)
        b = run_session(*meta_chunks_new, new_catalog)
        assert a.model_copy(update={"catalog_version": NEW}) == b

    same(
        synth.synth_session(
            synth.SynthConfig(
                reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=PREV
            )
        ),
        synth.synth_session(
            synth.SynthConfig(
                reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=NEW
            )
        ),
    )
    for ex, angle in (("PUSHUP", 75.0), ("SITUP", 110.0)):
        same(
            synth_floor.synth_session(
                synth_floor.FloorSynthConfig(ex, synth_floor.reps(3, angle), catalog_version=PREV)  # type: ignore[arg-type]
            ),
            synth_floor.synth_session(
                synth_floor.FloorSynthConfig(ex, synth_floor.reps(3, angle), catalog_version=NEW)  # type: ignore[arg-type]
            ),
        )
    for ex in OLD_MORE:
        rs = synth_floor.reps(3, OLD_MORE_ANGLE[ex])
        same(
            synth_more.synth_session(synth_more.MoreSynthConfig(ex, rs, catalog_version=PREV)),  # type: ignore[arg-type]
            synth_more.synth_session(synth_more.MoreSynthConfig(ex, rs, catalog_version=NEW)),  # type: ignore[arg-type]
        )


# --- 하이 니·마운틴 클라이머: 두 다리 = 1렙 (D-83, D-84) ---------------------------


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_pair_summary(new_catalog: Catalog, exercise: ExtraExercise) -> None:
    res = run(ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][0])), new_catalog)
    s = res.pose_summary.to_dict()
    assert s["legAsymmetryDeg"]["avg"] < 5.0
    assert s["repDurationMs"]["avg"] > 0
    for e in res.reps:
        d = e.to_dict()
        assert d["leftReason"] is None and d["rightReason"] is None
        assert d["startT"] < d["bottomT"] < d["endT"]


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_one_leg_shallow_fails_the_pair(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    """한쪽 다리만 기준을 넘으면 그 렙(쌍)은 미인정. 어느 다리가 모자랐는지 렙 결과에 남는다."""
    good, shallow, _ = ANGLES[exercise]
    res = run(ExtraSynthConfig(exercise, reps(3, good, right_angle=shallow)), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 3
    for e in res.reps:
        d = e.to_dict()
        assert e.reason is RepReason.SHALLOW_DEPTH
        assert d["leftReason"] is None and d["rightReason"] == "SHALLOW_DEPTH"


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_one_leg_only_is_not_counted(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    """왼다리만 계속 올리면 짝이 없어 렙이 되지 않는다."""
    cfg = ExtraSynthConfig(exercise, reps(5, ANGLES[exercise][0]), legs="left_only")
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 0 and res.recognized_reps == 0


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_both_legs_together_is_not_counted(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    """두 다리를 동시에 굽히면(스쿼트·웅크리기) 반대 다리가 펴져 있지 않아 미인정."""
    cfg = ExtraSynthConfig(exercise, reps(4, ANGLES[exercise][0]), legs="both")
    res = run(cfg, new_catalog)
    assert res.recognized_reps == 0
    assert res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_needs_both_legs_visible(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    """한쪽 다리가 계속 가려지면 쌍을 만들 수 없어 0회 (많이 세는 쪽으로는 틀리지 않음)."""
    from rep_engine.landmarks import Joint

    cfg = ExtraSynthConfig(
        exercise, reps(4, ANGLES[exercise][0]), hidden=frozenset({Joint.RIGHT_KNEE})
    )
    res = run(cfg, new_catalog)
    assert res.recognized_reps == 0


@pytest.mark.parametrize("exercise", ALTERNATING)
def test_us01_alternating_dropout_loses_only_that_rep(
    new_catalog: Catalog, exercise: ExtraExercise
) -> None:
    cfg = ExtraSynthConfig(exercise, reps(5, ANGLES[exercise][0]))
    _, mid, _ = rep_windows(cfg)[2]
    cfg.invalid_ranges = [(mid - 100, mid + 500)]
    res = run(cfg, new_catalog)
    assert res.recognized_reps == 4
    assert all(e.end_t < mid - 100 or e.start_t > mid + 500 for e in res.reps if e.accepted)


def test_us01_mountain_climber_needs_hands_on_floor(new_catalog: Catalog) -> None:
    """손을 바닥에서 떼고(누워서 무릎 당기기처럼) 하면 팔 지지 각도가 작아 미인정."""
    cfg = ExtraSynthConfig("MOUNTAIN_CLIMBER", reps(4, 95.0), arms="side")
    res = run(cfg, new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, MountainClimberRepEvent)
        assert e.reason is RepReason.SHALLOW_DEPTH
        assert e.min_arm_support_angle is not None and e.min_arm_support_angle < 130


def test_us01_unrealistic_pace_overridden_for_fast_exercises(new_catalog: Catalog) -> None:
    """하이 니 1렙(두 다리)은 약 0.8초라 공통 기준(1초)이면 UNREALISTIC_PACE가 된다 (D-87)."""
    cfg = ExtraSynthConfig("HIGH_KNEE", reps(6, 85.0))
    res_new = run(cfg, new_catalog)
    assert AnomalyCode.UNREALISTIC_PACE not in {a.code for a in res_new.anomalies}
    data = _catalog_data()
    del data["anomaly_by_exercise"]
    res_common = run(cfg, parse_catalog(data))
    assert res_common.recognized_reps == res_new.recognized_reps == 6
    assert AnomalyCode.UNREALISTIC_PACE in {a.code for a in res_common.anomalies}


def test_us01_anomaly_override_values_checked() -> None:
    data = _catalog_data()
    data["anomaly_by_exercise"]["high_knee"]["min_avg_rep_ms"] = -1
    with pytest.raises(ConfigError):
        parse_catalog(data)
    data = _catalog_data()
    data["anomaly_by_exercise"]["high_knee"]["unknown_key"] = 1
    with pytest.raises(ConfigError):
        parse_catalog(data)


# --- 슈퍼맨·돈키 킥: 비슷한 동작과 구별 (D-85, D-86) -------------------------------


def test_us01_superman_arms_at_sides_not_counted(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("SUPERMAN", reps(4, 155.0), arms="side"), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    for e in res.reps:
        assert isinstance(e, SupermanRepEvent)
        assert e.reason is RepReason.SHALLOW_DEPTH
        assert e.arm_reach_at_top is not None and e.arm_reach_at_top < 140


def test_us01_donkey_kick_without_hand_support_not_counted(new_catalog: Catalog) -> None:
    res = run(ExtraSynthConfig("DONKEY_KICK", reps(4, 20.0), arms="side"), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)


@pytest.mark.parametrize("declared", ["SUPERMAN", "DONKEY_KICK"])
def test_us01_glute_bridge_motion_not_counted_as(new_catalog: Catalog, declared: str) -> None:
    """누워서 엉덩이를 드는 글루트 브릿지 동작은 슈퍼맨·돈키 킥으로 세지 않는다 (팔 조건)."""
    meta, chunks = synth_more.synth_session(
        synth_more.MoreSynthConfig("GLUTE_BRIDGE", synth_floor.reps(5, 8.0), catalog_version=NEW)
    )
    res = run_session(meta.model_copy(update={"exercise_type": declared}), chunks, new_catalog)
    assert res.recognized_reps == 0


def test_us01_superman_arm_rule_is_what_rejects_bridge() -> None:
    """팔 뻗음 조건을 끄면 브릿지 동작이 슈퍼맨으로 세어진다 — 조건이 하는 일을 확인."""
    data = _catalog_data()
    data["superman"]["min_arm_reach_angle"] = 1
    meta, chunks = synth_more.synth_session(
        synth_more.MoreSynthConfig("GLUTE_BRIDGE", synth_floor.reps(5, 8.0), catalog_version=NEW)
    )
    res = run_session(
        meta.model_copy(update={"exercise_type": "SUPERMAN"}), chunks, parse_catalog(data)
    )
    assert res.recognized_reps > 0


# --- 자세 확인 (D-75): 고른 종목과 다른 자세로는 세지 않음 ------------------------


@pytest.mark.parametrize(
    ("motion", "declared"),
    [
        ("MOUNTAIN_CLIMBER", "HIGH_KNEE"),  # 엎드린 무릎 당기기를 하이 니로 → 엎드려서 무효
        ("HIGH_KNEE", "MOUNTAIN_CLIMBER"),  # 서서 무릎 올리기를 마운틴 클라이머로 → 서 있어 무효
        ("HIGH_KNEE", "DONKEY_KICK"),
        ("HIGH_KNEE", "SUPERMAN"),
    ],
)
def test_us01_extra_posture_wrong_exercise_is_not_counted(
    new_catalog: Catalog, motion: ExtraExercise, declared: str
) -> None:
    meta, chunks = synth_session(ExtraSynthConfig(motion, reps(5, ANGLES[motion][0])))
    res = run_session(meta.model_copy(update={"exercise_type": declared}), chunks, new_catalog)
    assert res.recognized_reps == 0


def test_us01_high_knee_lying_down_is_not_counted(new_catalog: Catalog) -> None:
    meta, chunks = _rotate_90(*synth_session(ExtraSynthConfig("HIGH_KNEE", reps(5, 85.0))))
    res = run_session(meta, chunks, new_catalog)
    assert res.recognized_reps == 0


# --- 서버 재계산 API ----------------------------------------------------------


def test_us01_recount_api_extra_exercises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    client = TestClient(app)
    expected_fields = {
        "HIGH_KNEE": ({"leftMinHipAngle", "rightMinHipAngle"}, "kneeDriveDeg"),
        "MOUNTAIN_CLIMBER": ({"leftMinTuckAngle", "minArmSupportAngle"}, "kneeTuckDeg"),
        "SUPERMAN": ({"minBodyArchAngle", "armReachAtTop"}, "bodyArchDeg"),
        "DONKEY_KICK": ({"maxKickHipAngle", "minArmSupportAngle"}, "kickHipAngleDeg"),
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


def test_us01_recount_api_older_catalog_rejects_high_knee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    meta, chunks = synth_session(ExtraSynthConfig("HIGH_KNEE", reps(2, 85.0), catalog_version=PREV))
    body = {
        "meta": meta.to_dict(),
        "chunks": [c.to_dict() for c in chunks],
        "client": {"clientRepCount": 2, "reps": [], "aiConfidence": 0.9, "poseSummary": None},
    }
    r = TestClient(app).post("/internal/recount", json=body, headers={"X-Internal-Token": "t"})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_FAILED"


# --- 웹캠 데모 (카메라·cv2 없이) ------------------------------------------------


@pytest.mark.parametrize("exercise", EXERCISES)
def test_demo_extra_exercise_reaches_goal_of_5(exercise: ExtraExercise) -> None:
    """키로 고른 새 운동도 그 운동으로 판정하고, 인정 5회에서 목표 달성이 된다 (D-88)."""
    from tools.synth_extra import synth_frames
    from tools.webcam_demo import ALL_EXERCISES, DEMO_CATALOG, EXTRA_EXERCISE_KEYS, Demo

    assert exercise in ALL_EXERCISES and exercise in dict(EXTRA_EXERCISE_KEYS)
    demo = Demo(720, 1280, "lite", "test", False, DEMO_CATALOG)
    assert demo.set_exercise(exercise, start_t=0)
    goal_seen_at: int | None = None
    for f in synth_frames(ExtraSynthConfig(exercise, reps(6, ANGLES[exercise][0]))):
        demo.push(f)
        if demo.goal_reached and goal_seen_at is None:
            goal_seen_at = demo.runner.counter.accepted_count
    assert goal_seen_at == 5
    assert len(demo.graph_lines()) == 3
    assert any(line.startswith("angle ") and line != "angle -" for line in demo.status_lines(15.0))
