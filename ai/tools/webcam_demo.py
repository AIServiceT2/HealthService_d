"""웹캠 실시간 데모. 판정은 rep_engine의 SessionRunner를 그대로 호출한다 (데모 전용 판정 로직 없음).

화면: 스켈레톤, 현재 kneeAngle, 상태, 인정/시도 수, 마지막 미인정 사유, 최근 5초 각도 그래프, FPS.
키: L 무작위 동작 확인 시작 · R 리셋 · S 세션 JSON 저장 · Q 종료

    python -m tools.webcam_demo                       # 카메라 0번
    python -m tools.webcam_demo --source data/videos/a.mp4 --headless   # 화면 없이 확인

OpenCV 기본 글꼴은 한글을 그리지 못해 화면에는 영문 상태명을 쓰고, 한국어 지시 문구는 로그로 낸다.
타임스탬프는 카메라면 시작 후 경과 시간(ms), 영상 파일이면 영상 시각을 쓴다.
"""

from __future__ import annotations

import argparse
import time
from collections import deque
from pathlib import Path
from typing import Any

from rep_engine.config import load_catalog
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
    ) -> None:
        self.catalog = load_catalog(catalog_version)
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

    def push(self, frame: Frame) -> list[RepEvent]:
        """프레임을 엔진에 넣는다. 세션 시각은 리셋 시점부터 다시 0에서 시작한다."""
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
        return events

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
    lms = frame.landmarks
    if lms is not None:
        pts = {
            i: (int(lm.x * w), int(lm.y * h))
            for i, lm in enumerate(lms)
            if lm is not None and lm.visibility >= demo.runner.cfg.features.min_visibility
        }
        for a, b in BONES:
            if a in pts and b in pts:
                cv2.line(img, pts[a], pts[b], GREEN, 3)
        for p in pts.values():
            cv2.circle(img, p, 4, WHITE, -1)
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
                demo = Demo(w, h, variant, mp.__version__, mirrored, catalog)
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
            demo.push(frame)
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
        "종료: 프레임 %d, 인정 %d / 시도 %d, 확신도 %.3f",
        n,
        res.recognized_reps,
        res.attempted_reps,
        res.ai_confidence,
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
    a = p.parse_args(argv)
    demo = run(a.source, a.model, a.mirrored, a.catalog, a.headless, a.max_frames, a.out)
    if a.save:
        demo.save(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
