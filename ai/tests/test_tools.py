"""tools/의 순수 함수 테스트 (mediapipe·opencv 없이 CI에서 돈다)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from rep_engine.config import ConfigError
from rep_engine.landmarks import MEDIAPIPE_FACE_INDICES
from rep_engine.schemas import CHUNK_SPEC, ChunkSpec, Frame, RepEvent
from rep_engine.validation import chunk_size_bytes
from tools import angle_study, calibrate_confidence, evaluate, make_sample_data, plot_session
from tools.common import load_session, save_session, split_chunks
from tools.extract_keypoints import Downsampler, landmarks_to_frame
from tools.synth import SynthConfig, synth_frames, synth_meta, varied_squats


@dataclass
class FakeLm:
    x: float
    y: float
    z: float
    visibility: float | None


def test_downsampler_30_to_15() -> None:
    d = Downsampler(15)
    taken = [i for i in range(90) if d.take(i * 1000 / 30)]
    assert len(taken) == 45 and taken[:3] == [0, 2, 4]
    d = Downsampler(15)
    # 29.97fps 300프레임: 마지막 t = 299 × 33.37 = 9976.6ms → 목표 시각 k × 66.67ms, k = 0..149
    assert sum(d.take(i * 1000 / 29.97) for i in range(300)) == 150


def test_landmarks_to_frame() -> None:
    pose = [FakeLm(0.5, 1.7, -0.1, 0.8) for _ in range(33)]
    pose[20] = FakeLm(-3.0, 0.2, 0.0, None)
    f = landmarks_to_frame(100, pose)
    assert f.landmarks is not None
    assert all(f.landmarks[i] is None for i in MEDIAPIPE_FACE_INDICES)
    lm = f.landmarks[20]
    assert lm is not None and lm.x == -1.0 and lm.visibility == 0.0
    assert landmarks_to_frame(5, None).landmarks is None
    with pytest.raises(ValueError):
        landmarks_to_frame(0, pose[:17])


def test_split_chunks_respects_both_limits(tmp_path: Path) -> None:
    sc = SynthConfig(reps=varied_squats(3, seed=1))
    frames = synth_frames(sc)
    chunks = split_chunks("s", frames)
    assert all(len(c.frames) <= CHUNK_SPEC.max_frames for c in chunks)
    assert all(chunk_size_bytes(c) <= CHUNK_SPEC.max_bytes for c in chunks)
    assert [f.t for c in chunks for f in c.frames] == [f.t for f in frames]
    small = split_chunks("s", frames, ChunkSpec(max_frames=7, max_bytes=262144))
    assert all(len(c.frames) <= 7 for c in small)
    save_session(tmp_path / "x.json", synth_meta(sc), chunks, {"note": 1})
    meta, again, extra = load_session(tmp_path / "x.json")
    assert again == chunks and extra == {"note": 1} and meta == synth_meta(sc)
    assert split_chunks("s", [Frame(t=0, landmarks=None)])[0].seq == 0


@pytest.fixture(scope="module")
def sample(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("data")
    labels = root / "labels_sample.csv"
    make_sample_data.main(["--n", "6", "--out", str(root / "keypoints"), "--labels", str(labels)])
    return labels


def test_evaluate_and_reports(sample: Path, tmp_path: Path) -> None:
    evals = evaluate.run_evaluation(sample, None)
    assert len(evals) == 6 and all(e.subject == "synthetic" for e in evals)
    side = [e for e in evals if e.view == "side"]
    assert side and all(e.exact for e in side)
    md = evaluate.report_markdown(evals, sample, None)
    assert "합성 데이터" in md and "촬영 각도별" in md
    r = evaluate.reason_metrics(evals)
    assert set(r) == {"shallow", "too_fast", "out_of_frame"}
    assert evaluate.main(["--labels", str(sample), "--out-dir", str(tmp_path), "--tag", "t"]) == 0
    assert list(tmp_path.glob("eval_*_t.csv")) and list(tmp_path.glob("eval_*_t.md"))


def test_evaluate_with_config_yaml(sample: Path) -> None:
    yaml_path = Path(__file__).resolve().parent.parent / "config/catalog/cat_2026-11-01.yaml"
    assert len(evaluate.run_evaluation(sample, str(yaml_path))) == 6
    with pytest.raises(ConfigError):
        evaluate.load_config("cat_1999-01-01")


def test_calibration_points_and_tool(sample: Path, tmp_path: Path) -> None:
    pts = calibrate_confidence.fit_points(
        [0.2, 0.5, 0.7, 0.9, 0.95], [False, False, True, True, True]
    )
    assert pts[0][0] == 0.0 and pts[-1][0] == 1.0
    assert all(b[0] > a[0] and b[1] >= a[1] for a, b in zip(pts, pts[1:], strict=False))
    calibrate_confidence.validate_points(pts, "cat_2026-11-01")
    table = calibrate_confidence.threshold_table([0.95, 0.85, 0.5], [True, False, True])
    assert table[0] == (0.80, 2 / 3, 0.5)
    assert calibrate_confidence.main(["--labels", str(sample), "--out-dir", str(tmp_path)]) == 0
    assert list(tmp_path.glob("calibration_*.png"))


def test_angle_study(sample: Path, tmp_path: Path) -> None:
    evals = evaluate.run_evaluation(sample, None)
    assert angle_study.recommend(evals, 99) is None
    assert angle_study.recommend(evals, 1) == ("side",)
    assert "근거 부족" in angle_study.report(evals, sample, 99)
    assert angle_study.main(["--labels", str(sample), "--out-dir", str(tmp_path)]) == 0


def test_plot_session(sample: Path, tmp_path: Path) -> None:
    session = next((sample.parent / "keypoints").glob("*.json"))
    out = plot_session.plot(session, tmp_path / "p.png")
    assert out.stat().st_size > 10_000


# --- webcam_demo 최저점 사진 (카메라·cv2 없이) ---------------------------------


def _demo_run(
    snapshot_dir: Path | None,
) -> tuple[list[tuple[Path, int, int]], list[RepEvent], str]:
    from tools.synth import RepSpec
    from tools.webcam_demo import Demo

    saved: list[tuple[Path, int, int]] = []

    def writer(path: Path, image: Any, frame: Frame, event: RepEvent) -> None:
        saved.append((path, int(image[0]), frame.t))

    sc = SynthConfig(
        reps=[RepSpec(85, 2000), RepSpec(90, 2200), RepSpec(125, 2000), RepSpec(80, 2400)],
        noise_px=1.5,
    )
    demo = Demo(720, 1280, "lite", "test", False, "cat_2026-11-01", snapshot_dir, writer)
    events: list[RepEvent] = []
    for f in synth_frames(sc):
        events += demo.push(f, np.array([f.t]))  # 이미지 대신 "어느 시각 프레임인지"를 담은 배열
    return saved, events, demo.meta.session_id


def test_snapshot_saves_bottom_frame_of_accepted_reps_only(tmp_path: Path) -> None:
    saved, events, session_id = _demo_run(tmp_path)
    accepted = [e for e in events if e.accepted]
    assert len(events) == 4 and len(accepted) == 3  # 얕은 렙 1개는 사진 없음
    assert len(saved) == 3
    for (path, image_t, frame_t), e in zip(saved, accepted, strict=True):
        assert image_t == frame_t == e.bottom_t  # 엔진이 정한 최저점 프레임
        assert path == tmp_path / session_id / f"rep{e.index:02d}_{e.min_knee_angle:.1f}deg.jpg"


def test_snapshot_off_by_default() -> None:
    saved, events, _ = _demo_run(None)
    assert saved == [] and sum(e.accepted for e in events) == 3


def test_bottom_snapshot_rules() -> None:
    from tests.featurize import make_rep
    from tools.webcam_demo import BottomSnapshot

    b = BottomSnapshot()
    fr = Frame(t=0, landmarks=None)
    b.observe(True, 100, 120.0, np.array([100]), fr)
    b.observe(True, 166, 90.0, np.array([166]), fr)
    b.observe(True, 233, 95.0, np.array([233]), fr)  # 더 깊지 않으면 유지
    b.observe(True, 300, None, np.array([300]), fr)  # 무효 프레임은 무시
    picked = b.take(make_rep(start=0, dur=332))  # bottom_t = 166
    assert picked is not None and int(picked[0][0]) == 166
    assert b.take(make_rep(start=0, dur=400)) is None  # bottom_t 200 ≠ 166 → 저장 안 함
    b.observe(False, 400, 170.0, np.array([400]), fr)  # 렙 밖 → 후보 버림
    assert b.image is None and b.take(make_rep(start=0, dur=332)) is None
