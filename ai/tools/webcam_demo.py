"""웹캠 실시간 데모. 판정은 rep_engine의 SessionRunner를 그대로 호출한다 (데모 전용 판정 로직 없음).

화면: 스켈레톤, 현재 kneeAngle, 상태, 인정/시도 수, 마지막 미인정 사유, 최근 5초 각도 그래프, FPS.
키: L 무작위 동작 확인 시작 · R 리셋 · S 세션 JSON 저장 · Q 종료

    python -m tools.webcam_demo                       # 카메라 0번
    python -m tools.webcam_demo --snapshots           # 인정 렙마다 최저점 사진 저장
    python -m tools.webcam_demo --source data/videos/a.mp4 --headless   # 화면 없이 확인

`--snapshots`: 인정된 렙마다 가장 깊이 앉은 순간(엔진의 bottomT 프레임) 사진 1장을
`~/Downloads/jeonunsi_snapshots/<세션ID>/`에 저장한다 (흐림 없음, 얼굴이 나올 수 있음).
PC 개발 도구 전용이다. 앱은 영상을 저장하지 않는다 (PRD 2절, US-01, DECISIONS D-65).

OpenCV 기본 글꼴은 한글을 그리지 못해 화면에는 영문 상태명을 쓰고, 한국어 지시 문구는 로그로 낸다.
타임스탬프는 카메라면 시작 후 경과 시간(ms), 영상 파일이면 영상 시각을 쓴다.
"""

from __future__ import annotations

import argparse
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rep_engine.config import load_catalog
from rep_engine.counters.squat import ASCENDING, DESCENDING
from rep_engine.liveness import issue_challenge
from rep_engine.schemas import (
    Device,
    Frame,
    LivenessChallenge,
    Platform,
    RepEvent,
    SessionMeta,
)
from rep_engine.session import SessionRunner
from tools.common import DATA_DIR, save_session, setup_logging, split_chunks
from tools.download_models import VARIANTS, model_path
from tools.extract_keypoints import DEFAULT_CATALOG, MP_MODEL_VERSION, landmarks_to_frame

GRAPH_WINDOW_MS = 5000
LIVENESS_WINDOW_MS = 10000
SNAPSHOT_DIR = Path.home() / "Downloads" / "jeonunsi_snapshots"
#: 렙이 진행 중인 상태 (이 동안 최저점 후보 프레임을 들고 있음)
IN_REP_STATES = frozenset({DESCENDING, ASCENDING})
# 화면 그리기용 (판정과 무관)
GREEN, RED, WHITE, YELLOW, GRAY = (
    (80, 220, 80),
    (60, 60, 230),
    (255, 255, 255),
    (0, 220, 255),
    (
        120,
        120,
        120,
    ),
)
BONES = [
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (24, 26),
    (26, 28),
]


SnapshotWriter = Callable[[Path, Any, Frame, RepEvent], None]


class BottomSnapshot:
    """렙 진행 중 무릎 각도가 가장 작았던 프레임 1장(이미지 + 관절)만 들고 있다.

    렙은 일어선 뒤에야 인정으로 확정되므로, 확정될 때까지 최저점 후보를 하나만 보관한다.
    판정 엔진과 같은 규칙(더 작을 때만 갱신)을 써서 엔진의 bottomT와 같은 프레임을 고른다.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.image: Any | None = None
        self.frame: Frame | None = None
        self.t: int | None = None
        self.angle: float | None = None

    def observe(
        self, in_rep: bool, t: int, angle: float | None, image: Any | None, frame: Frame
    ) -> None:
        """프레임 1개를 본다. 렙 밖이면 후보를 버린다."""
        if not in_rep:
            self.reset()
            return
        if angle is None or image is None:
            return
        if self.angle is None or angle < self.angle:
            self.image = image.copy()
            self.frame = frame
            self.t = t
            self.angle = angle

    def take(self, event: RepEvent) -> tuple[Any, Frame] | None:
        """인정 렙의 최저점(bottomT) 사진. 보관 중인 프레임과 시각이 다르면 None."""
        if self.image is None or self.frame is None or self.t != event.bottom_t:
            return None
        return self.image, self.frame


def snapshot_path(directory: Path, session_id: str, event: RepEvent) -> Path:
    """`<폴더>/<세션ID>/rep03_86.2deg.jpg`"""
    return directory / session_id / f"rep{event.index:02d}_{event.min_knee_angle:.1f}deg.jpg"


def draw_skeleton(img: Any, frame: Frame, min_visibility: float) -> None:
    """관절 선을 이미지 위에 그린다 (화면·사진 공용)."""
    import cv2

    h, w = img.shape[:2]
    lms = frame.landmarks
    if lms is None:
        return
    pts = {
        i: (int(lm.x * w), int(lm.y * h))
        for i, lm in enumerate(lms)
        if lm is not None and lm.visibility >= min_visibility
    }
    for a, b in BONES:
        if a in pts and b in pts:
            cv2.line(img, pts[a], pts[b], GREEN, 3)
    for p in pts.values():
        cv2.circle(img, p, 4, WHITE, -1)


def write_snapshot(
    path: Path, image: Any, frame: Frame, event: RepEvent, min_visibility: float
) -> None:
    """최저점 사진에 스켈레톤과 렙 번호·최저 무릎 각도를 그려 JPEG로 저장한다."""
    import cv2

    out = image.copy()
    draw_skeleton(out, frame, min_visibility)
    label = f"rep {event.index} | min knee {event.min_knee_angle:.1f} deg | accepted"
    cv2.putText(out, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
    cv2.putText(out, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, YELLOW, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), out):
        raise OSError(f"사진 저장 실패: {path}")


class Demo:
    """세션 상태 (리셋하면 새 SessionRunner)."""

    def __init__(
        self,
        width: int,
        height: int,
        variant: str,
        mp_version: str,
        mirrored: bool,
        catalog_version: str,
        snapshot_dir: Path | None = None,
        snapshot_writer: SnapshotWriter | None = None,
    ) -> None:
        self.catalog = load_catalog(catalog_version)
        self.snapshot_dir = snapshot_dir
        self._writer: SnapshotWriter = snapshot_writer or (
            lambda path, img, fr, ev: write_snapshot(
                path, img, fr, ev, self.runner.cfg.features.min_visibility
            )
        )
        self.snapshots: list[Path] = []
        self._bottom = BottomSnapshot()
        self.width, self.height = width, height
        self.mirrored = mirrored
        self.model_version = MP_MODEL_VERSION.format(variant=variant, mp=mp_version)
        self.log = setup_logging()
        self.reset(start_t=0)

    def _meta(self, liveness: LivenessChallenge | None) -> SessionMeta:
        return SessionMeta(
            session_id=f"demo-{int(time.time())}",
            exercise_type="SQUAT",
            catalog_version=self.catalog.version,
            fps=15,
            image_width=self.width,
            image_height=self.height,
            mirrored=self.mirrored,
            device=Device(platform=Platform.ANDROID, model_version=self.model_version),
            liveness=liveness,
        )

    def reset(self, start_t: int, liveness: bool = False) -> None:
        challenge: LivenessChallenge | None = None
        if liveness:
            issued = issue_challenge()
            challenge = LivenessChallenge(
                challenge_id=issued.challenge_id,
                action=issued.action,
                issued_at_t=start_t,
                expires_at_t=start_t + LIVENESS_WINDOW_MS,
            )
            self.log.info("무작위 동작: %s (%s)", issued.instruction, issued.action.value)
        self.meta = self._meta(challenge)
        self.runner = SessionRunner(self.meta, self.catalog)
        self.frames: list[Frame] = []
        self.angles: deque[tuple[int, float]] = deque()
        self.last_reason: str = "-"
        self.t_offset = start_t
        self._bottom.reset()

    def push(self, frame: Frame, image: Any | None = None) -> list[RepEvent]:
        """프레임을 엔진에 넣는다. 세션 시각은 리셋 시점부터 다시 0에서 시작한다.

        `image`(BGR)를 주고 사진 저장이 켜져 있으면, 인정 렙의 최저점 사진을 저장한다.
        """
        local = Frame(t=frame.t - self.t_offset, landmarks=frame.landmarks)
        if self.frames and local.t <= self.frames[-1].t:
            return []
        self.frames.append(local)
        events = self.runner.push(local)
        f = self.runner.last_features
        if f is not None and f.knee_angle is not None:
            self.angles.append((local.t, f.knee_angle))
        while self.angles and local.t - self.angles[0][0] > GRAPH_WINDOW_MS:
            self.angles.popleft()
        for e in events:
            if not e.accepted and e.reason is not None:
                self.last_reason = e.reason.value
            self.log.info(
                "렙 %d: %s %s (최저 %.1f°)",
                e.index,
                "인정" if e.accepted else "미인정",
                e.reason.value if e.reason else "",
                e.min_knee_angle,
            )
            if e.accepted and self.snapshot_dir is not None:
                self._save_snapshot(e)
        # 렙 확정(위)을 먼저 처리한 뒤 다음 최저점 후보를 갱신한다
        knee = f.knee_angle if f is not None else None
        in_rep = self.runner.counting and self.runner.counter.state in IN_REP_STATES
        self._bottom.observe(in_rep, local.t, knee, image, local)
        return events

    def _save_snapshot(self, event: RepEvent) -> None:
        picked = self._bottom.take(event)
        if picked is None or self.snapshot_dir is None:
            self.log.warning("렙 %d: 최저점 프레임을 찾지 못해 사진을 저장하지 않음", event.index)
            return
        path = snapshot_path(self.snapshot_dir, self.meta.session_id, event)
        self._writer(path, picked[0], picked[1], event)
        self.snapshots.append(path)
        self.log.info("사진 저장: %s", path)

    def save(self, out_dir: Path) -> Path:
        out = out_dir / f"{self.meta.session_id}.json"
        save_session(out, self.meta, split_chunks(self.meta.session_id, self.frames))
        self.log.info("저장: %s (프레임 %d)", out, len(self.frames))
        return out

    def status_lines(self, fps: float) -> list[str]:
        r = self.runner
        angle = r.counter.current_angle
        lv = r.liveness_result
        lv_text = (
            "-"
            if self.meta.liveness is None
            else (lv.status.value if lv else f"WAIT {self.meta.liveness.action.value}")
        )
        return [
            f"knee {angle:.1f} deg" if angle is not None else "knee -",
            f"state {r.counter.state}{'' if r.counting else ' (liveness)'}",
            f"accepted {r.counter.accepted_count} / attempted {len(r.reps)}",
            f"last reason {self.last_reason}",
            f"liveness {lv_text}",
            f"fps {fps:.1f}",
        ]


def _draw(img: Any, frame: Frame, demo: Demo, fps: float) -> None:
    import cv2

    h, w = img.shape[:2]
    draw_skeleton(img, frame, demo.runner.cfg.features.min_visibility)
    for i, line in enumerate(demo.status_lines(fps)):
        cv2.putText(img, line, (10, 28 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, YELLOW, 2)
    # 최근 5초 각도 그래프 (0~180°)
    gx, gy, gw, gh = 10, h - 130, min(360, w - 20), 120
    cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), GRAY, 1)
    sq = demo.runner.cfg.squat
    for ang, color in (
        (sq.stand_angle, WHITE),
        (sq.attempt_angle, YELLOW),
        (sq.depth_accept_angle, GREEN),
    ):
        y = int(gy + gh - ang / 180.0 * gh)
        cv2.line(img, (gx, y), (gx + gw, y), color, 1)
    if len(demo.angles) >= 2:
        t_end = demo.angles[-1][0]
        pts_g = [
            (int(gx + gw - (t_end - t) / GRAPH_WINDOW_MS * gw), int(gy + gh - a / 180.0 * gh))
            for t, a in demo.angles
        ]
        for p0, p1 in zip(pts_g, pts_g[1:], strict=False):
            cv2.line(img, p0, p1, RED, 2)


def run(
    source: str,
    variant: str,
    mirrored: bool,
    catalog: str,
    headless: bool,
    max_frames: int | None,
    out_dir: Path,
    snapshot_dir: Path | None = None,
) -> Demo:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    log = setup_logging()
    is_camera = source.isdigit()
    cap = cv2.VideoCapture(int(source) if is_camera else source)
    if not cap.isOpened():
        raise RuntimeError(f"입력을 열 수 없음: {source}")
    mpath = model_path(variant)
    if not mpath.is_file():
        raise FileNotFoundError(f"모델 없음: {mpath} — 먼저 python -m tools.download_models")
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(mpath)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    demo: Demo | None = None
    t_start = time.perf_counter()
    last_tick, fps, n = t_start, 0.0, 0
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while max_frames is None or n < max_frames:
            ok, bgr = cap.read()
            if not ok:
                break
            if is_camera and mirrored:
                bgr = cv2.flip(bgr, 1)
            h, w = bgr.shape[:2]
            if demo is None:
                demo = Demo(w, h, variant, mp.__version__, mirrored, catalog, snapshot_dir)
            t_ms = (
                round((time.perf_counter() - t_start) * 1000)
                if is_camera
                else round(cap.get(cv2.CAP_PROP_POS_MSEC))
            )
            image = mp.Image(
                image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            )
            result = landmarker.detect_for_video(image, t_ms)
            frame = landmarks_to_frame(
                t_ms, result.pose_landmarks[0] if result.pose_landmarks else None
            )
            demo.push(frame, bgr)  # 화면 글자를 그리기 전 원본을 넘긴다
            n += 1
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last_tick, 1e-6))
            last_tick = now
            if headless:
                continue
            _draw(bgr, frame, demo, fps)
            cv2.imshow("jeonunsi rep_engine demo", bgr)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("r"), ord("R")):
                demo.reset(start_t=t_ms)
            elif key in (ord("l"), ord("L")):
                demo.reset(start_t=t_ms, liveness=True)
            elif key in (ord("s"), ord("S")):
                demo.save(out_dir)
    cap.release()
    if not headless:
        cv2.destroyAllWindows()
    if demo is None:
        raise RuntimeError("읽은 프레임이 없음")
    res = demo.runner.finish()
    log.info(
        "종료: 프레임 %d, 인정 %d / 시도 %d, 확신도 %.3f, 사진 %d장",
        n,
        res.recognized_reps,
        res.attempted_reps,
        res.ai_confidence,
        len(demo.snapshots),
    )
    return demo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="웹캠 실시간 렙 판정 데모 (rep_engine 그대로 사용)")
    p.add_argument("--source", default="0", help="카메라 번호(기본 0) 또는 영상 파일 경로")
    p.add_argument("--model", choices=VARIANTS, default="lite")
    p.add_argument(
        "--mirrored",
        action="store_true",
        help="카메라 화면을 거울처럼 뒤집어 보여 주고 meta.mirrored=true로 저장",
    )
    p.add_argument("--catalog", default=DEFAULT_CATALOG)
    p.add_argument("--headless", action="store_true", help="창 없이 실행 (확인용)")
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--save", action="store_true", help="끝날 때 세션 JSON 저장")
    p.add_argument("--out", type=Path, default=DATA_DIR / "keypoints" / "webcam")
    p.add_argument(
        "--snapshots", action="store_true", help="인정 렙마다 최저점 사진 1장 저장 (흐림 없음)"
    )
    p.add_argument(
        "--snapshot-dir", type=Path, default=SNAPSHOT_DIR, help=f"사진 폴더 (기본 {SNAPSHOT_DIR})"
    )
    a = p.parse_args(argv)
    demo = run(
        a.source,
        a.model,
        a.mirrored,
        a.catalog,
        a.headless,
        a.max_frames,
        a.out,
        a.snapshot_dir if a.snapshots else None,
    )
    if a.save:
        demo.save(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
