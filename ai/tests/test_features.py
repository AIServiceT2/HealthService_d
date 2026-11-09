import pytest

from rep_engine.adapters import Point, SkeletonFrame
from rep_engine.config import EngineConfig
from rep_engine.features.extractor import FeatureExtractor
from rep_engine.features.filters import OneEuroFilter
from rep_engine.features.geometry import (
    angle_deg,
    distance,
    midpoint,
    tilt_from_vertical_deg,
    to_pixel,
)
from rep_engine.landmarks import Joint
from tests.featurize import features
from tests.synth import RepSpec, SynthConfig


# --- 기하 ---------------------------------------------------------------------
def test_known_angles() -> None:
    assert angle_deg((0, 0), (1, 0), (2, 0)) == pytest.approx(180.0)
    assert angle_deg((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)
    assert angle_deg((1, 1), (0, 0), (1, 0)) == pytest.approx(45.0)
    assert angle_deg((0, 0), (0, 0), (1, 0)) is None


def test_tilt_and_helpers() -> None:
    assert tilt_from_vertical_deg((0, 0), (0, 10)) == pytest.approx(0.0)
    assert tilt_from_vertical_deg((0, 0), (10, 10)) == pytest.approx(45.0)
    assert tilt_from_vertical_deg((5, 5), (5, 5)) is None
    assert distance((0, 0), (3, 4)) == 5.0
    assert midpoint((0, 0), (2, 4)) == (1.0, 2.0)


def test_aspect_ratio_correction_matters() -> None:
    # 픽셀 공간에서 직각인 세 점을 정규화하면, 보정 없이 계산한 각도는 90°가 아니다
    w, h = 720, 1280
    a_px, b_px, c_px = (360.0, 400.0), (360.0, 800.0), (760.0 - 300.0, 800.0)
    a, b, c = ((x / w, y / h) for x, y in (a_px, b_px, c_px))
    corrected = angle_deg(to_pixel(*a, w, h), to_pixel(*b, w, h), to_pixel(*c, w, h))
    naive = angle_deg(a, b, c)
    assert corrected == pytest.approx(90.0)
    assert naive is not None and abs(naive - 90.0) < 1e-9  # 직각은 축 정렬이라 그대로
    # 기울어진 경우 차이가 난다
    c2_px = (560.0, 600.0)
    c2 = (c2_px[0] / w, c2_px[1] / h)
    corr2 = angle_deg(a_px, b_px, c2_px)
    naive2 = angle_deg(a, b, c2)
    assert corr2 is not None and naive2 is not None
    assert abs(corr2 - naive2) > 5.0


# --- 필터 ---------------------------------------------------------------------
def test_one_euro_deterministic_and_smooths() -> None:
    seq = [(i * 66, 100 + (5 if i % 2 else -5)) for i in range(40)]
    f1, f2 = OneEuroFilter(1.0, 0.05, 1.0), OneEuroFilter(1.0, 0.05, 1.0)
    out1 = [f1(v, t) for t, v in seq]
    out2 = [f2(v, t) for t, v in seq]
    assert out1 == out2
    assert max(out1[10:]) - min(out1[10:]) < 10  # 떨림이 줄어듦


def test_one_euro_reset_and_same_time() -> None:
    f = OneEuroFilter(1.0, 0.0, 1.0)
    assert f(10.0, 0) == 10.0
    y = f(20.0, 66)
    assert 10.0 < y < 20.0
    assert f(99.0, 66) == y  # 같은 시각은 이전 출력
    f.reset()
    assert f(50.0, 1000) == 50.0


# --- 추출기 -------------------------------------------------------------------
def _sk(t: int, vis_left: float, vis_right: float, bend_right: bool = False) -> SkeletonFrame:
    j: list[Point | None] = [None] * 13
    j[Joint.LEFT_SHOULDER] = Point(100, 100, 0.9)
    j[Joint.RIGHT_SHOULDER] = Point(140, 100, 0.9)
    for hip, knee, ankle, x, vis in (
        (Joint.LEFT_HIP, Joint.LEFT_KNEE, Joint.LEFT_ANKLE, 100, vis_left),
        (Joint.RIGHT_HIP, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE, 140, vis_right),
    ):
        j[hip] = Point(x, 300, vis)
        kx = x + (200 if bend_right and hip == Joint.RIGHT_HIP else 0)
        j[knee] = Point(kx, 500 if kx == x else 300, vis)
        j[ankle] = Point(x, 700, vis)
    return SkeletonFrame(t, tuple(j))


def test_side_selection(cfg: EngineConfig) -> None:
    ex = FeatureExtractor(cfg.features, cfg.squat.stand_angle)
    both = ex.update(_sk(0, 0.9, 0.9))
    assert both.valid and both.knee_angle == pytest.approx(180.0)
    assert both.knee_asymmetry == pytest.approx(0.0)
    one = FeatureExtractor(cfg.features, cfg.squat.stand_angle).update(
        _sk(0, 0.9, 0.1, bend_right=True)
    )
    assert one.valid and one.knee_angle == pytest.approx(180.0) and one.knee_asymmetry is None
    avg = FeatureExtractor(cfg.features, cfg.squat.stand_angle).update(
        _sk(0, 0.9, 0.9, bend_right=True)
    )
    # 오른쪽 무릎을 옆으로 뺀 프레임: 오른쪽 각도 < 180 → 평균은 두 값의 중간
    assert avg.knee_angle_raw is not None and 90 < avg.knee_angle_raw < 180
    assert avg.knee_asymmetry is not None and avg.knee_asymmetry > 50
    none = ex.update(_sk(66, 0.1, 0.1))
    assert not none.valid and none.knee_angle is None
    assert not ex.update(SkeletonFrame(132, None)).valid


def test_trunk_lean_upright(cfg: EngineConfig) -> None:
    f = FeatureExtractor(cfg.features, cfg.squat.stand_angle).update(_sk(0, 0.9, 0.9))
    assert f.trunk_lean == pytest.approx(0.0)
    assert f.torso_leg_ratio == pytest.approx(200 / 400)


def test_synthetic_side_angle_matches_target(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[RepSpec(bottom_angle=90, duration_ms=4000)], lead_in_ms=2000)
    feats = features(sc, cfg)
    raws = [f.knee_angle_raw for f in feats if f.knee_angle_raw is not None]
    assert min(raws) == pytest.approx(90.0, abs=1.0)
    assert max(raws) == pytest.approx(175.0, abs=0.5)


def test_baseline_and_hip_drop_front(cfg: EngineConfig) -> None:
    sc = SynthConfig(view="front", reps=[RepSpec(bottom_angle=80, duration_ms=3000)])
    feats = features(sc, cfg)
    drops = [f.hip_drop for f in feats if f.hip_drop is not None]
    first_with_drop = next(f.t for f in feats if f.hip_drop is not None)
    assert first_with_drop >= cfg.features.calibration_window_ms
    assert max(drops) > cfg.squat.hip_drop_accept
    # 정면에서는 2D 무릎 각도가 깊이 기준까지 내려가지 않는다
    angles = [f.knee_angle for f in feats if f.knee_angle is not None]
    assert min(angles) > cfg.squat.depth_accept_angle
    assert min(angles) < cfg.squat.attempt_angle


def test_filter_resets_after_gap(cfg: EngineConfig) -> None:
    # 2초 서 있다가 1초 사라졌다 다시 나타남 → 재등장 첫 프레임은 필터 없이 원본 값
    sc = SynthConfig(
        reps=[RepSpec(bottom_angle=90, duration_ms=3000)],
        lead_in_ms=2000,
        invalid_ranges=[(2500, 3500)],
    )
    feats = features(sc, cfg)
    back = next(f for f in feats if f.t >= 3500 and f.valid)
    assert back.knee_angle == back.knee_angle_raw


def test_calibration_broken_by_invalid(cfg: EngineConfig) -> None:
    sc = SynthConfig(reps=[], lead_in_ms=1800, tail_ms=0, invalid_ranges=[(600, 700)])
    feats = features(sc, cfg)
    assert all(f.hip_drop is None for f in feats if f.t < 700 + cfg.features.calibration_window_ms)
    assert any(f.hip_drop is not None for f in feats)
