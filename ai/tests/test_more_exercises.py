"""런지·인버티드 숄더 프레스·글루트 브릿지·사이드 레그 리프트 판정.

합성 데이터, 기준값은 cat_2026-11-17의 [가정] 값.

US-01 "가동범위 기준에 못 미친 렙은 미인정"을 종목만 바꿔 확인한다. 이 종목들은 MVP 범위
밖이며(mvp-scope.md) 엔진에만 있다 (DECISIONS D-71~D-77).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from rep_engine.config import DEFAULT_CATALOG_DIR, Catalog, load_catalog, parse_catalog
from rep_engine.counters.base import make_counter, registered_exercises
from rep_engine.counters.glute_bridge import GluteBridgeCounter
from rep_engine.counters.inverted_shoulder_press import InvertedShoulderPressCounter
from rep_engine.counters.lunge import LungeCounter
from rep_engine.counters.side_leg_lift import SideLegLiftCounter
from rep_engine.errors import ConfigError, UnsupportedExerciseError
from rep_engine.landmarks import Joint
from rep_engine.schemas import (
    Chunk,
    FormTag,
    GluteBridgePoseSummary,
    GluteBridgeRepEvent,
    InvertedShoulderPressPoseSummary,
    InvertedShoulderPressRepEvent,
    Landmark,
    LungePoseSummary,
    LungeRepEvent,
    PushupRepEvent,
    RepReason,
    SessionMeta,
    SessionResult,
    SideLegLiftPoseSummary,
    SideLegLiftRepEvent,
    SitupRepEvent,
)
from rep_engine.session import run_session
from service.app import TOKEN_ENV, app
from tools import synth
from tools.synth_floor import FloorSynthConfig, reps
from tools.synth_floor import synth_session as floor_session
from tools.synth_more import MoreExercise, MoreSynthConfig, rep_windows, synth_session

NEW = "cat_2026-11-17"
PREV = "cat_2026-11-10"
OLD = "cat_2026-11-01"
#: 종목별 판정 각도 (인정되는 최저 각도, 가동범위 미달 각도, 시도로도 안 치는 각도).
#: 글루트 브릿지는 엉덩이 굽힘(180 − 엉덩이 내각): 8 = 내각 172°, 20 = 160°, 30 = 150°
#: 사이드 레그 리프트는 180 − 다리 벌림: 140 = 40° 벌림, 155 = 25°, 165 = 15°
ANGLES: dict[MoreExercise, tuple[float, float, float]] = {
    "LUNGE": (88.0, 115.0, 150.0),
    "INVERTED_SHOULDER_PRESS": (80.0, 110.0, 140.0),
    "GLUTE_BRIDGE": (8.0, 20.0, 30.0),
    "SIDE_LEG_LIFT": (140.0, 155.0, 165.0),
}
EXERCISES: list[MoreExercise] = [
    "LUNGE",
    "INVERTED_SHOULDER_PRESS",
    "GLUTE_BRIDGE",
    "SIDE_LEG_LIFT",
]
EVENT_TYPES = {
    "LUNGE": LungeRepEvent,
    "INVERTED_SHOULDER_PRESS": InvertedShoulderPressRepEvent,
    "GLUTE_BRIDGE": GluteBridgeRepEvent,
    "SIDE_LEG_LIFT": SideLegLiftRepEvent,
}
SUMMARY_TYPES = {
    "LUNGE": LungePoseSummary,
    "INVERTED_SHOULDER_PRESS": InvertedShoulderPressPoseSummary,
    "GLUTE_BRIDGE": GluteBridgePoseSummary,
    "SIDE_LEG_LIFT": SideLegLiftPoseSummary,
}
SECTIONS = {
    "LUNGE": "lunge",
    "INVERTED_SHOULDER_PRESS": "inverted_shoulder_press",
    "GLUTE_BRIDGE": "glute_bridge",
    "SIDE_LEG_LIFT": "side_leg_lift",
}


@pytest.fixture(scope="module")
def new_catalog() -> Catalog:
    return load_catalog(NEW)


def run(cfg: MoreSynthConfig, catalog: Catalog) -> SessionResult:
    meta, chunks = synth_session(cfg)
    return run_session(meta, chunks, catalog)


def _without_posture() -> Catalog:
    """cat_2026-11-17에서 자세 확인(posture)만 뺀 카탈로그."""
    data: dict[str, Any] = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    del data["posture"]
    return parse_catalog(data)


def _rotate_90(meta: SessionMeta, chunks: list[Chunk]) -> tuple[SessionMeta, list[Chunk]]:
    """세션 전체를 시계 방향으로 90° 돌린다 (서 있던 사람이 누운 것처럼 보임).

    픽셀 (px, py) → (H − py, px). 정규화 좌표로는 (x, y) → (1 − y, x), 화면 가로·세로가 바뀐다.
    관절 각도는 그대로라 자세 확인이 없으면 같은 렙으로 세어진다.
    """

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


# --- 세 종목 공통 -------------------------------------------------------------


@pytest.mark.parametrize("model", ["mediapipe", "movenet"])
@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_normal_reps_are_counted(
    new_catalog: Catalog, exercise: MoreExercise, model: synth.Model
) -> None:
    good = ANGLES[exercise][0]
    res = run(MoreSynthConfig(exercise, reps(5, good), model=model, noise_px=1.0), new_catalog)
    assert res.recognized_reps == 5 and res.attempted_reps == 5
    for e in res.reps:
        assert e.accepted and e.reason is None
        assert abs(e.depth_angle - good) < 2.0
    assert all(isinstance(e, EVENT_TYPES[exercise]) for e in res.reps)
    assert isinstance(res.pose_summary, SUMMARY_TYPES[exercise])


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_models_and_mirroring_agree(new_catalog: Catalog, exercise: MoreExercise) -> None:
    good = ANGLES[exercise][0]
    base = run(MoreSynthConfig(exercise, reps(4, good)), new_catalog)
    movenet = run(MoreSynthConfig(exercise, reps(4, good), model="movenet"), new_catalog)
    mirrored = run(MoreSynthConfig(exercise, reps(4, good), mirrored=True), new_catalog)
    assert base.reps == movenet.reps == mirrored.reps


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_shallow_reps_not_accepted(new_catalog: Catalog, exercise: MoreExercise) -> None:
    res = run(MoreSynthConfig(exercise, reps(4, ANGLES[exercise][1])), new_catalog)
    assert res.recognized_reps == 0 and res.attempted_reps == 4
    assert all(e.reason is RepReason.SHALLOW_DEPTH for e in res.reps)
    assert FormTag.SHALLOW_DEPTH_FREQUENT in res.pose_summary.form_tags


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_small_motion_is_not_an_attempt(
    new_catalog: Catalog, exercise: MoreExercise
) -> None:
    res = run(MoreSynthConfig(exercise, reps(3, ANGLES[exercise][2])), new_catalog)
    assert res.attempted_reps == 0


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_too_fast(new_catalog: Catalog, exercise: MoreExercise) -> None:
    res = run(MoreSynthConfig(exercise, reps(3, ANGLES[exercise][0], duration_ms=500)), new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    assert all(e.reason is RepReason.TOO_FAST for e in res.reps)


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_out_of_frame(new_catalog: Catalog, exercise: MoreExercise) -> None:
    cfg = MoreSynthConfig(exercise, reps(5, ANGLES[exercise][0]))
    _, bottom, _ = rep_windows(cfg)[2]
    cfg.invalid_ranges = [(bottom - 100, bottom + 1300)]
    res = run(cfg, new_catalog)
    assert [e.reason for e in res.reps] == [None, None, RepReason.OUT_OF_FRAME, None, None]
    assert res.recognized_reps == 4


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_result_json_roundtrip(new_catalog: Catalog, exercise: MoreExercise) -> None:
    """종목별 렙·요약 모양이 JSON만으로 다시 구별된다 (백엔드가 같은 스키마로 읽을 수 있음)."""
    res = run(MoreSynthConfig(exercise, reps(3, ANGLES[exercise][0])), new_catalog)
    assert SessionResult.model_validate(res.to_dict()) == res


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_is_deterministic(new_catalog: Catalog, exercise: MoreExercise) -> None:
    cfg = MoreSynthConfig(exercise, reps(4, ANGLES[exercise][0]), noise_px=2.0, seed=7)
    assert run(cfg, new_catalog).to_dict() == run(cfg, new_catalog).to_dict()


@pytest.mark.parametrize("catalog_version", [PREV, OLD])
@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_older_catalogs_reject_new_exercises(
    exercise: MoreExercise, catalog_version: str
) -> None:
    cfg = MoreSynthConfig(exercise, reps(2, ANGLES[exercise][0]), catalog_version=catalog_version)
    with pytest.raises(UnsupportedExerciseError) as exc:
        run(cfg, load_catalog(catalog_version))
    assert exc.value.code == "VALIDATION_FAILED"


@pytest.mark.parametrize("exercise", EXERCISES)
def test_us01_more_config_order_checked(exercise: MoreExercise) -> None:
    data: dict[str, Any] = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    section = SECTIONS[exercise]
    data[section]["attempt_angle"] = data[section]["flex_start_angle"] + 1  # 순서 어김
    with pytest.raises(ConfigError):
        parse_catalog(data)


def test_us01_more_counters_registered(new_catalog: Catalog) -> None:
    assert {"LUNGE", "INVERTED_SHOULDER_PRESS", "GLUTE_BRIDGE", "SIDE_LEG_LIFT"} <= set(
        registered_exercises()
    )
    cfg = new_catalog.for_model("mediapipe")
    assert isinstance(make_counter("LUNGE", cfg), LungeCounter)
    assert isinstance(make_counter("INVERTED_SHOULDER_PRESS", cfg), InvertedShoulderPressCounter)
    assert isinstance(make_counter("GLUTE_BRIDGE", cfg), GluteBridgeCounter)
    assert isinstance(make_counter("SIDE_LEG_LIFT", cfg), SideLegLiftCounter)


# --- 새 카탈로그가 기존 종목을 바꾸지 않음 -----------------------------------


def test_us01_new_catalog_keeps_existing_sections() -> None:
    """cat_2026-11-17은 cat_2026-11-10에 세 종목·자세 확인 섹션만 더했다 (기존 기준값은 그대로)."""
    prev = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{PREV}.yaml").read_text())
    new = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    added = set(new) - set(prev)
    assert added == {"lunge", "inverted_shoulder_press", "glute_bridge", "side_leg_lift", "posture"}
    for key in prev:
        if key == "catalog_version":
            continue
        if key == "features":  # 가시도 기준만 낮춤 0.5 → 0.3 (D-80)
            assert {k: v for k, v in new[key].items() if k != "min_visibility"} == {
                k: v for k, v in prev[key].items() if k != "min_visibility"
            }
            assert (prev[key]["min_visibility"], new[key]["min_visibility"]) == (0.5, 0.3)
            continue
        if key == "model_overrides":  # MoveNet 가시도 기준만 낮춤 0.3 → 0.2 (D-80)
            assert new[key]["movenet"]["features"]["min_visibility"] == 0.2
            assert prev[key]["movenet"]["features"]["min_visibility"] == 0.3
            continue
        if key == "situp":  # 발 뜸 기준 한 줄만 더함 (D-82)
            assert {k: v for k, v in new[key].items() if k != "feet_down"} == prev[key]
            assert new[key]["feet_down"]["max_foot_lift_ratio"] == 0.15
            continue
        if key == "pushup":  # 무릎 기준 한 줄만 더함 (D-78)
            assert {k: v for k, v in new[key].items() if k != "min_knee_angle"} == prev[key]
            assert new[key]["min_knee_angle"] == 160
            continue
        assert new[key] == prev[key], key


def test_us01_existing_exercises_same_on_new_catalog(new_catalog: Catalog) -> None:
    sc_prev = synth.SynthConfig(
        reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=PREV
    )
    sc_new = synth.SynthConfig(
        reps=synth.varied_squats(5, seed=3), noise_px=1.5, catalog_version=NEW
    )
    prev = run_session(*synth.synth_session(sc_prev), load_catalog(PREV))
    new = run_session(*synth.synth_session(sc_new), new_catalog)
    assert prev.model_copy(update={"catalog_version": NEW}) == new
    for exercise in ("PUSHUP", "SITUP"):
        fp = run_session(
            *floor_session(FloorSynthConfig(exercise, reps(3, 100), catalog_version=PREV)),
            load_catalog(PREV),
        )
        fn = run_session(
            *floor_session(FloorSynthConfig(exercise, reps(3, 100), catalog_version=NEW)),
            new_catalog,
        )
        if exercise == "SITUP":  # 새 카탈로그만 maxFootLift를 채운다 (D-82). 판정은 같아야 함
            fn = fn.model_copy(
                update={"reps": [e.model_copy(update={"max_foot_lift": None}) for e in fn.reps]}
            )
        assert fp.model_copy(update={"catalog_version": NEW}) == fn


# --- 런지 --------------------------------------------------------------------


def test_us01_lunge_summary(new_catalog: Catalog) -> None:
    res = run(MoreSynthConfig("LUNGE", reps(4, 90)), new_catalog)
    e = res.reps[0]
    # 합성 런지: 뒷다리 엉덩이는 180°, 앞다리 엉덩이는 무릎 각도와 같다 → 차 = 180 − 무릎 각도
    assert isinstance(e, LungeRepEvent) and e.hip_spread_at_bottom is not None
    assert abs(e.hip_spread_at_bottom - (180.0 - e.min_knee_angle)) < 2.0
    ps = res.pose_summary
    assert isinstance(ps, LungePoseSummary) and ps.lunge_knee_flexion_deg is not None
    assert abs(ps.lunge_knee_flexion_deg.avg - (180.0 - e.min_knee_angle)) < 0.5


def test_us01_lunge_squat_stance_is_not_a_lunge(new_catalog: Catalog) -> None:
    """두 다리를 같게 굽히면(스쿼트처럼) 무릎은 충분히 굽어도 런지로 인정하지 않는다."""
    res = run(MoreSynthConfig("LUNGE", reps(4, 88), stance="squat"), new_catalog)
    assert res.attempted_reps == 4 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, LungeRepEvent) and e.hip_spread_at_bottom is not None
        assert e.min_knee_angle <= 100.0 and e.hip_spread_at_bottom < 40.0
        assert e.reason is RepReason.SHALLOW_DEPTH


def test_us01_lunge_hip_spread_unmeasurable_is_out_of_frame(new_catalog: Catalog) -> None:
    """한쪽 어깨가 안 보여 좌우 엉덩이 각도 차를 못 재면 OUT_OF_FRAME (인정하지 않음)."""
    hidden = frozenset({Joint.RIGHT_SHOULDER})
    res = run(MoreSynthConfig("LUNGE", reps(3, 88), hidden=hidden), new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, LungeRepEvent) and e.hip_spread_at_bottom is None
        assert e.reason is RepReason.OUT_OF_FRAME


# --- 인버티드 숄더 프레스 -------------------------------------------------------


def test_us01_shoulder_press_summary(new_catalog: Catalog) -> None:
    res = run(MoreSynthConfig("INVERTED_SHOULDER_PRESS", reps(4, 80)), new_catalog)
    e = res.reps[0]
    assert isinstance(e, InvertedShoulderPressRepEvent) and e.min_pike_hip_angle is not None
    assert abs(e.min_pike_hip_angle - 95.0) < 2.0
    assert e.knee_angle_at_bottom is not None and e.knee_angle_at_bottom > 175.0
    ps = res.pose_summary
    assert isinstance(ps, InvertedShoulderPressPoseSummary) and ps.pike_hip_angle_deg is not None
    assert FormTag.ELBOW_ASYMMETRY not in ps.form_tags


def test_us01_shoulder_press_plain_pushup_is_not_counted(new_catalog: Catalog) -> None:
    """엉덩이를 접지 않은 일반 푸시업 자세는 팔꿈치를 충분히 굽혀도 세지 않는다.

    자세 확인(D-75)에서 상체가 거꾸로가 아니라 프레임이 무효가 되어 시도로도 기록되지 않는다.
    """
    cfg = MoreSynthConfig("INVERTED_SHOULDER_PRESS", reps(4, 80), pike_hip_deg=178.0)
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 0 and res.recognized_reps == 0


def test_us01_shoulder_press_pike_rule_without_posture(new_catalog: Catalog) -> None:
    """자세 확인을 끈 카탈로그에서도 파이크 조건(D-72)만으로 일반 푸시업은 인정되지 않는다."""
    catalog = _without_posture()
    cfg = MoreSynthConfig("INVERTED_SHOULDER_PRESS", reps(4, 80), pike_hip_deg=178.0)
    res = run(cfg, catalog)
    assert res.attempted_reps == 4 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, InvertedShoulderPressRepEvent) and e.min_pike_hip_angle is not None
        assert e.min_elbow_angle <= 90.0 and e.min_pike_hip_angle > 110.0
        assert e.reason is RepReason.SHALLOW_DEPTH


def test_us01_shoulder_press_hip_never_visible_is_out_of_frame(new_catalog: Catalog) -> None:
    """엉덩이 각도를 한 번도 못 재면(발목이 안 보임) OUT_OF_FRAME."""
    hidden = frozenset({Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE})
    res = run(MoreSynthConfig("INVERTED_SHOULDER_PRESS", reps(3, 80), hidden=hidden), new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, InvertedShoulderPressRepEvent) and e.min_pike_hip_angle is None
        assert e.reason is RepReason.OUT_OF_FRAME


# --- 글루트 브릿지 ----------------------------------------------------------------


def test_us01_glute_bridge_summary(new_catalog: Catalog) -> None:
    res = run(MoreSynthConfig("GLUTE_BRIDGE", reps(4, 8)), new_catalog)
    e = res.reps[0]
    assert isinstance(e, GluteBridgeRepEvent)
    assert e.start_t < e.bottom_t < e.end_t
    assert e.knee_angle_at_top is not None and 80.0 < e.knee_angle_at_top < 120.0
    ps = res.pose_summary
    assert isinstance(ps, GluteBridgePoseSummary) and ps.top_hip_flexion_deg is not None
    assert abs(ps.top_hip_flexion_deg.avg - e.min_hip_flexion) < 1.0


def test_us01_glute_bridge_lying_still_is_not_a_rep(new_catalog: Catalog) -> None:
    """누운 채 가만히 있으면 렙이 없다 (판정 각도가 쉬는 자세 기준보다 큼)."""
    res = run(MoreSynthConfig("GLUTE_BRIDGE", [], tail_ms=5000), new_catalog)
    assert res.attempted_reps == 0


def test_us01_recount_api_new_exercises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    client = TestClient(app)
    expected_fields = {
        "LUNGE": ({"minKneeAngle", "hipSpreadAtBottom"}, "lungeKneeFlexionDeg"),
        "INVERTED_SHOULDER_PRESS": ({"minElbowAngle", "minPikeHipAngle"}, "pikeHipAngleDeg"),
        "GLUTE_BRIDGE": ({"minHipFlexion", "kneeAngleAtTop"}, "topHipFlexionDeg"),
        "SIDE_LEG_LIFT": ({"maxLegSpread", "kneeAngleAtTop"}, "legSpreadDeg"),
    }
    for exercise in EXERCISES:
        meta, chunks = synth_session(MoreSynthConfig(exercise, reps(5, ANGLES[exercise][0])))
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


def test_us01_recount_api_old_catalog_rejects_lunge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "t")
    meta, chunks = synth_session(
        MoreSynthConfig("LUNGE", reps(2, ANGLES["LUNGE"][0]), catalog_version=PREV)
    )
    body = {
        "meta": meta.to_dict(),
        "chunks": [c.to_dict() for c in chunks],
        "client": {"clientRepCount": 2, "reps": [], "aiConfidence": 0.9, "poseSummary": None},
    }
    r = TestClient(app).post("/internal/recount", json=body, headers={"X-Internal-Token": "t"})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION_FAILED"


# --- 자세 확인 (D-75): 고른 종목과 다른 자세로는 세지 않음 ------------------------
#: (만든 동작, 그 동작의 인정 각도) — 아래 표의 '다른 종목으로 보냄'에 쓴다
MOTIONS: dict[MoreExercise, float] = {e: ANGLES[e][0] for e in EXERCISES}


@pytest.mark.parametrize(
    ("motion", "declared"),
    [
        ("LUNGE", "GLUTE_BRIDGE"),  # 서서 굽히기를 브릿지로 → 서 있으므로 무효
        ("INVERTED_SHOULDER_PRESS", "PUSHUP"),  # 파이크를 푸시업으로 → 거꾸로라 무효
        ("INVERTED_SHOULDER_PRESS", "SQUAT"),
        ("GLUTE_BRIDGE", "LUNGE"),
    ],
)
def test_us01_posture_wrong_exercise_is_not_counted(
    new_catalog: Catalog, motion: MoreExercise, declared: str
) -> None:
    meta, chunks = synth_session(MoreSynthConfig(motion, reps(5, MOTIONS[motion])))
    res = run_session(meta.model_copy(update={"exercise_type": declared}), chunks, new_catalog)
    assert res.recognized_reps == 0


def test_us01_posture_off_in_older_catalog_counts_lunge_as_bridge() -> None:
    """자세 확인이 없으면(옛 방식) 서서 하는 런지 동작이 브릿지로 세어질 수 있었다 — 고친 문제."""
    meta, chunks = synth_session(MoreSynthConfig("LUNGE", reps(5, MOTIONS["LUNGE"])))
    res = run_session(
        meta.model_copy(update={"exercise_type": "GLUTE_BRIDGE"}), chunks, _without_posture()
    )
    assert res.recognized_reps > 0


@pytest.mark.parametrize("exercise", ["LUNGE", "SQUAT"])
def test_us01_posture_lying_down_squat_or_lunge_is_not_counted(
    new_catalog: Catalog, exercise: str
) -> None:
    """같은 관절 움직임을 누운 자세로(화면을 90° 돌려) 하면 서는 종목으로 세지 않는다."""
    if exercise == "LUNGE":
        meta, chunks = synth_session(MoreSynthConfig("LUNGE", reps(5, MOTIONS["LUNGE"])))
    else:
        sc = synth.SynthConfig(reps=synth.varied_squats(5, seed=3), catalog_version=NEW)
        meta, chunks = synth.synth_session(sc)
    upright = run_session(meta, chunks, new_catalog)
    lying = run_session(*_rotate_90(meta, chunks), new_catalog)
    lying_no_check = run_session(*_rotate_90(meta, chunks), _without_posture())
    assert upright.recognized_reps == 5
    assert lying.attempted_reps == 0
    assert lying_no_check.recognized_reps == 5  # 자세 확인이 없으면 각도만 보고 셌을 것
    assert lying.ai_confidence < upright.ai_confidence  # 무효 프레임이라 확신도도 낮아짐


def test_us01_posture_unmeasurable_torso_is_invalid(new_catalog: Catalog) -> None:
    """어깨가 모두 안 보여 상체 방향을 못 재면 무효 (가려서 자세 확인을 피할 수 없음)."""
    hidden = frozenset({Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER})
    res = run(MoreSynthConfig("GLUTE_BRIDGE", reps(3, 8), hidden=hidden), new_catalog)
    assert res.attempted_reps == 0


def test_us01_posture_config_order_checked() -> None:
    data: dict[str, Any] = yaml.safe_load((DEFAULT_CATALOG_DIR / f"{NEW}.yaml").read_text())
    data["posture"]["lunge"] = {"min_deg": 50, "max_deg": 10}
    with pytest.raises(ConfigError):
        parse_catalog(data)


def test_us01_posture_absent_in_older_catalogs() -> None:
    assert load_catalog(PREV).base.posture is None
    assert load_catalog(OLD).base.posture is None
    new = load_catalog(NEW).base.posture
    assert new is not None and new.situp is None  # 윗몸 일으키기는 확인하지 않음 (D-75)


# --- 사이드 레그 리프트 (D-77) -----------------------------------------------------


def test_us01_side_leg_lift_summary(new_catalog: Catalog) -> None:
    res = run(MoreSynthConfig("SIDE_LEG_LIFT", reps(4, 140)), new_catalog)
    e = res.reps[0]
    assert isinstance(e, SideLegLiftRepEvent)
    assert abs(e.max_leg_spread - 40.0) < 2.0 and abs(e.depth_angle - 140.0) < 2.0
    assert e.knee_angle_at_top is not None and e.knee_angle_at_top > 175.0
    ps = res.pose_summary
    assert isinstance(ps, SideLegLiftPoseSummary) and ps.leg_spread_deg is not None
    assert abs(ps.leg_spread_deg.avg - e.max_leg_spread) < 1.0


def test_us01_side_leg_lift_needs_both_legs(new_catalog: Catalog) -> None:
    """다리 벌림은 두 다리가 다 보여야 잰다. 한쪽 발목이 안 보이면 렙이 생기지 않는다."""
    hidden = frozenset({Joint.RIGHT_ANKLE})
    res = run(MoreSynthConfig("SIDE_LEG_LIFT", reps(3, 140), hidden=hidden), new_catalog)
    assert res.attempted_reps == 0


def test_us01_side_leg_lift_standing_is_not_counted(new_catalog: Catalog) -> None:
    """같은 다리 벌림을 서서(화면을 90° 돌려) 하면 누운 자세가 아니라 세지 않는다 (D-75)."""
    meta, chunks = synth_session(MoreSynthConfig("SIDE_LEG_LIFT", reps(5, 140)))
    lying = run_session(meta, chunks, new_catalog)
    standing = run_session(*_rotate_90(meta, chunks), new_catalog)
    standing_no_check = run_session(*_rotate_90(meta, chunks), _without_posture())
    assert lying.recognized_reps == 5
    assert standing.attempted_reps == 0
    assert standing_no_check.recognized_reps == 5


# --- 무릎 대고 하는 푸시업 (D-78) · 점프 런지 (D-79) ----------------------------------


@pytest.mark.parametrize("knees", ["flat", "raised"])
def test_us01_knee_pushup_is_not_counted(new_catalog: Catalog, knees: str) -> None:
    """무릎을 바닥에 대고 하면 팔꿈치를 충분히 굽혀도 인정하지 않는다 (새 카탈로그)."""
    cfg = FloorSynthConfig("PUSHUP", reps(5, 75), knees=knees, catalog_version=NEW)  # type: ignore[arg-type]
    res = run_session(*floor_session(cfg), new_catalog)
    assert res.attempted_reps == 5 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, PushupRepEvent) and e.min_knee_angle_in_rep is not None
        assert e.min_elbow_angle <= 90.0 and e.min_knee_angle_in_rep < 160.0
        assert e.reason is RepReason.SHALLOW_DEPTH


def test_us01_knee_pushup_counted_without_knee_rule() -> None:
    """무릎 기준이 없는 옛 카탈로그(cat_2026-11-10)는 무릎 푸시업도 셌다 — 고친 문제를 기록."""
    cfg = FloorSynthConfig("PUSHUP", reps(5, 75), knees="flat", catalog_version=PREV)
    res = run_session(*floor_session(cfg), load_catalog(PREV))
    assert res.recognized_reps == 5


def test_us01_straight_leg_pushup_still_counted(new_catalog: Catalog) -> None:
    cfg = FloorSynthConfig("PUSHUP", reps(5, 75), noise_px=1.0, catalog_version=NEW)
    res = run_session(*floor_session(cfg), new_catalog)
    assert res.recognized_reps == 5
    for e in res.reps:
        assert isinstance(e, PushupRepEvent) and e.min_knee_angle_in_rep is not None
        assert e.min_knee_angle_in_rep > 170.0


def test_us01_pushup_legs_never_visible_is_out_of_frame(new_catalog: Catalog) -> None:
    """무릎 기준이 있으면 다리를 한 번도 못 본 렙은 OUT_OF_FRAME (가려서 피할 수 없음)."""
    knees = {25, 26}  # MediaPipe 왼·오른 무릎 (synth_floor는 MediaPipe 33 형식)
    cfg = FloorSynthConfig("PUSHUP", reps(3, 75), catalog_version=NEW)
    meta, chunks = floor_session(cfg)
    chunks = [
        c.model_copy(
            update={
                "frames": [
                    f
                    if f.landmarks is None
                    else f.model_copy(
                        update={
                            "landmarks": [
                                None if i in knees else lm for i, lm in enumerate(f.landmarks)
                            ]
                        }
                    )
                    for f in c.frames
                ]
            }
        )
        for c in chunks
    ]
    res = run_session(meta, chunks, new_catalog)
    assert res.attempted_reps == 3 and res.recognized_reps == 0
    assert all(e.reason is RepReason.OUT_OF_FRAME for e in res.reps)


@pytest.mark.parametrize("jump_height", [0.15, 0.3])
def test_us01_jumping_lunge_is_not_counted(new_catalog: Catalog, jump_height: float) -> None:
    """런지 자세로 점프하면 착지 뒤 렙은 인정하지 않는다. 첫 렙(선 자세에서 내려감)만 인정된다."""
    cfg = MoreSynthConfig("LUNGE", reps(5, 88), jump_height=jump_height, noise_px=1.0)
    res = run(cfg, new_catalog)
    assert res.attempted_reps == 5 and res.recognized_reps == 1
    first, *rest = res.reps
    assert first.accepted
    for e in rest:
        assert isinstance(e, LungeRepEvent) and e.max_foot_lift is not None
        assert e.max_foot_lift > 0.08 and e.reason is RepReason.SHALLOW_DEPTH


def test_us01_normal_lunge_feet_stay_down(new_catalog: Catalog) -> None:
    res = run(MoreSynthConfig("LUNGE", reps(5, 88), noise_px=2.0, seed=4), new_catalog)
    assert res.recognized_reps == 5
    for e in res.reps:
        assert isinstance(e, LungeRepEvent) and e.max_foot_lift is not None
        assert e.max_foot_lift < 0.03


# --- 관절 가시도 기준 낮춤 (D-80) -------------------------------------------------


@pytest.mark.parametrize("exercise", ["PUSHUP", "SITUP"])
def test_us01_low_visibility_joints_used_on_new_catalog(
    new_catalog: Catalog, exercise: str
) -> None:
    """가시도 0.4로 잡힌 관절(가늘고 긴 다리 등)도 새 카탈로그는 쓰고, 옛 카탈로그는 버렸다."""
    angle = 75.0 if exercise == "PUSHUP" else 110.0
    new = run_session(
        *floor_session(
            FloorSynthConfig(exercise, reps(5, angle), visibility=0.4, catalog_version=NEW)  # type: ignore[arg-type]
        ),
        new_catalog,
    )
    prev = run_session(
        *floor_session(
            FloorSynthConfig(exercise, reps(5, angle), visibility=0.4, catalog_version=PREV)  # type: ignore[arg-type]
        ),
        load_catalog(PREV),
    )
    assert new.recognized_reps == 5
    assert prev.attempted_reps == 0


def test_us01_very_low_visibility_still_ignored(new_catalog: Catalog) -> None:
    """가시도 0.2(기준 0.3 미만)는 여전히 버린다 — 너무 불확실한 좌표로 세지 않음."""
    res = run(MoreSynthConfig("LUNGE", reps(5, 88), visibility=0.2), new_catalog)
    assert res.attempted_reps == 0


# --- 윗몸 일으키기: 다리를 들어 배에 붙이기 (D-82) -------------------------------------


@pytest.mark.parametrize(("torso", "legs_lift"), [(165.0, 70.0), (170.0, 90.0)])
def test_us01_situp_pulling_legs_to_belly_is_not_counted(
    new_catalog: Catalog, torso: float, legs_lift: float
) -> None:
    """상체는 조금(10~15°)만 들고 다리를 배 쪽으로 당기면 인정하지 않는다 (발이 뜸)."""
    cfg = FloorSynthConfig(
        "SITUP", reps(5, torso), legs_lift_deg=legs_lift, noise_px=1.0, catalog_version=NEW
    )
    res = run_session(*floor_session(cfg), new_catalog)
    assert res.attempted_reps == 5 and res.recognized_reps == 0
    for e in res.reps:
        assert isinstance(e, SitupRepEvent) and e.max_foot_lift is not None
        assert e.min_torso_angle <= 120.0  # 각도만 보면 통과했을 렙
        assert e.max_foot_lift > 0.15 and e.reason is RepReason.SHALLOW_DEPTH


def test_us01_situp_pulling_legs_counted_on_older_catalog() -> None:
    """발 뜸 기준이 없는 옛 카탈로그는 이 동작도 셌다 — 고친 문제를 기록."""
    cfg = FloorSynthConfig("SITUP", reps(5, 165), legs_lift_deg=70, catalog_version=PREV)
    res = run_session(*floor_session(cfg), load_catalog(PREV))
    assert res.recognized_reps == 5


@pytest.mark.parametrize("legs_lift", [0.0, 4.0])
def test_us01_situp_normal_with_feet_down_still_counted(
    new_catalog: Catalog, legs_lift: float
) -> None:
    """정상 윗몸 일으키기는 그대로 인정. 발이 살짝(다리 길이 15% 이하) 뜨는 것은 허용."""
    cfg = FloorSynthConfig(
        "SITUP", reps(5, 110), legs_lift_deg=legs_lift, noise_px=1.0, catalog_version=NEW
    )
    res = run_session(*floor_session(cfg), new_catalog)
    assert res.recognized_reps == 5
    for e in res.reps:
        assert isinstance(e, SitupRepEvent) and e.max_foot_lift is not None
        assert e.max_foot_lift <= 0.15
