"""영상(또는 폴더) → 세션 JSON (SessionMeta + Chunk[]).

MediaPipe Tasks `PoseLandmarker`(VIDEO 모드)로 관절을 뽑고 `--fps`로 다운샘플링한다.
여러 사람이 있으면 첫 번째 사람만 쓴다. 얼굴 랜드마크(0~10)는 null로 비운다 (D-07).
청크는 프레임 수·바이트 제한을 모두 지키게 나눈다 (D-06).

    python -m tools.extract_keypoints data/videos/squat01.mp4 --model full
    python -m tools.extract_keypoints data/videos/ --model lite --out data/keypoints
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from rep_engine.landmarks import MEDIAPIPE_FACE_INDICES, MEDIAPIPE_NUM_LANDMARKS
from rep_engine.schemas import (
    COORD_MAX,
    COORD_MIN,
    Device,
    Frame,
    Landmark,
    Platform,
    SessionMeta,
)
from tools.common import DATA_DIR, save_session, setup_logging, split_chunks
from tools.download_models import VARIANTS, model_path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
DEFAULT_CATALOG = "cat_2026-11-01"
MP_MODEL_VERSION = "mediapipe-pose-{variant}@{mp}"


class _NormLandmark(Protocol):
    x: float
    y: float
    z: float
    visibility: float | None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def landmarks_to_frame(t_ms: int, pose: Sequence[_NormLandmark] | None) -> Frame:
    """MediaPipe 결과 1명분 → Frame. 얼굴 인덱스는 null, 값은 스키마 범위로 자른다."""
    if pose is None:
        return Frame(t=t_ms, landmarks=None)
    if len(pose) != MEDIAPIPE_NUM_LANDMARKS:
        raise ValueError(f"MediaPipe 관절 수가 {len(pose)}개 (33개여야 함)")
    out: list[Landmark | None] = []
    for i, lm in enumerate(pose):
        if i in MEDIAPIPE_FACE_INDICES:
            out.append(None)
            continue
        out.append(
            Landmark(
                x=_clamp(lm.x, COORD_MIN, COORD_MAX),
                y=_clamp(lm.y, COORD_MIN, COORD_MAX),
                z=lm.z,
                visibility=_clamp(lm.visibility or 0.0, 0.0, 1.0),
            )
        )
    return Frame(t=t_ms, landmarks=out)


class Downsampler:
    """원본 프레임 시각(ms)을 받아 target_fps 간격마다 처음 도달한 프레임만 고른다.

    고르는 판단과 다음 목표 시각으로 넘기는 판단에 같은 허용 오차를 써서,
    부동소수 오차로 이웃 프레임이 함께 뽑히지 않게 한다.
    """

    EPS_MS = 1e-6

    def __init__(self, target_fps: int) -> None:
        self.step = 1000.0 / target_fps
        self.next_t = 0.0

    def take(self, t_ms: float) -> bool:
        if t_ms + self.EPS_MS < self.next_t:
            return False
        while self.next_t <= t_ms + self.EPS_MS:
            self.next_t += self.step
        return True


@dataclass
class Extraction:
    meta: SessionMeta
    frames: list[Frame]
    infer_ms: list[float]


def _iter_video(path: Path, target_fps: int) -> Iterator[tuple[int, Any, int, int]]:
    """(t_ms, RGB 프레임, 너비, 높이)를 target_fps로 내보낸다."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없음: {path}")
    video_fps = cap.get(cv2.CAP_PROP_FPS) or float(target_fps)
    idx = 0
    sampler = Downsampler(target_fps)
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            t = idx * 1000.0 / video_fps
            idx += 1
            if not sampler.take(t):
                continue
            h, w = bgr.shape[:2]
            yield round(t), cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), w, h
    finally:
        cap.release()


def extract(
    video: Path,
    variant: str = "full",
    fps: int = 15,
    mirrored: bool = False,
    catalog_version: str = DEFAULT_CATALOG,
    session_id: str | None = None,
) -> Extraction:
    """영상 1개에서 관절을 뽑는다 (프레임당 추론 시간 ms도 잰다)."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    mpath = model_path(variant)
    if not mpath.is_file():
        raise FileNotFoundError(f"모델 없음: {mpath} — 먼저 python -m tools.download_models")
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(mpath)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    frames: list[Frame] = []
    infer_ms: list[float] = []
    width = height = 0
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for t_ms, rgb, w, h in _iter_video(video, fps):
            width, height = w, h
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            t0 = time.perf_counter()
            result = landmarker.detect_for_video(image, t_ms)
            infer_ms.append((time.perf_counter() - t0) * 1000.0)
            pose = result.pose_landmarks[0] if result.pose_landmarks else None
            frames.append(landmarks_to_frame(t_ms, pose))
    if not frames:
        raise RuntimeError(f"읽은 프레임이 없음: {video}")
    meta = SessionMeta(
        session_id=session_id or video.stem,
        exercise_type="SQUAT",
        catalog_version=catalog_version,
        fps=fps,
        image_width=width,
        image_height=height,
        mirrored=mirrored,
        device=Device(
            platform=Platform.ANDROID,
            model_version=MP_MODEL_VERSION.format(variant=variant, mp=mp.__version__),
        ),
        liveness=None,
    )
    return Extraction(meta, frames, infer_ms)


def videos_in(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    return [path]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="영상 → 세션 JSON (MediaPipe Pose Landmarker)")
    p.add_argument("input", type=Path, help="영상 파일 또는 폴더")
    p.add_argument("--model", choices=VARIANTS, default="full")
    p.add_argument("--fps", type=int, default=15, help="다운샘플링 fps (기본 15)")
    p.add_argument("--mirrored", action="store_true", help="영상이 좌우 반전(셀피 미러)되어 있음")
    p.add_argument("--catalog", default=DEFAULT_CATALOG, help="meta.catalogVersion")
    p.add_argument("--out", type=Path, default=DATA_DIR / "keypoints", help="출력 폴더")
    a = p.parse_args(argv)
    log = setup_logging()
    for video in videos_in(a.input):
        ex = extract(video, a.model, a.fps, a.mirrored, a.catalog)
        chunks = split_chunks(ex.meta.session_id, ex.frames)
        out = a.out / f"{video.stem}.json"
        save_session(out, ex.meta, chunks)
        detected = sum(f.landmarks is not None for f in ex.frames)
        avg = sum(ex.infer_ms) / len(ex.infer_ms)
        log.info(
            "%s → %s: 프레임 %d (사람 검출 %d), 청크 %d, 추론 평균 %.1f ms/프레임",
            video.name,
            out,
            len(ex.frames),
            detected,
            len(chunks),
            avg,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
