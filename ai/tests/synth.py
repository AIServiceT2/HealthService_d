"""합성 스쿼트 세션 생성기 (테스트·도구 공용).

서 있는 사람의 관절을 3D(좌우 X, 위 Y, 앞 Z, 단위 = 몸 길이)로 만들고, 무릎 내각을
시간에 따라 바꿔 엉덩이·무릎·발목을 기하학적으로 계산한 뒤 화면에 투영한다.

- 측면(`view="side"`): 화면 가로 = Z. 2D 무릎 내각 = 지정한 각도.
- 정면(`view="front"`): 화면 가로 = X. 무릎이 바깥으로 벌어져
  2D 각도는 덜 작아지고 엉덩이가 내려간다.

출력은 모델 원본 형식(MediaPipe 33 / MoveNet 17)이며 얼굴 인덱스는 null이다.
모든 무작위성은 `seed`로 고정한다.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from rep_engine.landmarks import (
    MEDIAPIPE_FACE_INDICES,
    MEDIAPIPE_INDEX,
    MEDIAPIPE_NUM_LANDMARKS,
    MIRROR_OF,
    MOVENET_FACE_INDICES,
    MOVENET_INDEX,
    MOVENET_NUM_LANDMARKS,
    Joint,
)
from rep_engine.schemas import (
    Chunk,
    Device,
    Frame,
    Landmark,
    LivenessAction,
    LivenessChallenge,
    Platform,
    SessionMeta,
)

Hand = Literal["LEFT", "RIGHT", "BOTH"]
View = Literal["side", "front"]
Model = Literal["mediapipe", "movenet"]

STAND_ANGLE = 175.0
MODEL_VERSIONS: dict[Model, str] = {
    "mediapipe": "mediapipe-pose-full@0.10",
    "movenet": "movenet-lightning@4",
}
#: 모델별 기본 청크 프레임 수 (256KB 안에 들어가게, DECISIONS D-06)
CHUNK_FRAMES: dict[Model, int] = {"mediapipe": 100, "movenet": 200}

# 몸 치수 (단위: 몸 길이 비율)
THIGH = 0.45
SHIN = 0.45
TORSO = 0.5
UPPER_ARM = 0.3
FOREARM = 0.27
HIP_HALF = 0.1
SHOULDER_HALF = 0.18
KNEE_SPLAY = 0.12  # 정면에서 무릎이 바깥으로 벌어지는 정도
SHIN_SHARE = 0.4  # 굽힘 중 정강이 기울기 몫 (나머지는 허벅지)
LEAN_SHARE = 0.3  # 굽힘 대비 상체 숙임
SIDE_DEPTH_OFFSET = 0.03  # 측면에서 좌우 다리를 구분하는 작은 화면 오프셋


@dataclass
class RepSpec:
    """렙 1개: 최저 무릎 내각(도), 렙 시간(ms), 렙 뒤 휴식(ms), 하강 비율."""

    bottom_angle: float = 80.0
    duration_ms: int = 2000
    rest_ms: int = 800
    descent_frac: float = 0.5


@dataclass
class SynthConfig:
    reps: list[RepSpec] = field(default_factory=list)
    fps: int = 15
    image_width: int = 720
    image_height: int = 1280
    view: View = "side"
    model: Model = "mediapipe"
    mirrored: bool = False
    noise_px: float = 0.0
    seed: int = 0
    lead_in_ms: int = 2000
    tail_ms: int = 1500
    visibility: float = 0.9
    #: [start, end) ms 동안 사람 미검출 (landmarks=null)
    invalid_ranges: list[tuple[int, int]] = field(default_factory=list)
    #: [start, end) ms 동안 손 들기
    hand_raises: list[tuple[int, int, Hand]] = field(default_factory=list)
    #: (시작 ms, 상체 배율): 그 시각부터 상체 길이를 바꿈 (사람 교체 흉내)
    torso_scale_from: tuple[int, float] | None = None
    #: [start, end) ms 동안 직전 프레임 좌표를 그대로 복사 (얼어붙은 관절)
    frozen_ranges: list[tuple[int, int]] = field(default_factory=list)
    #: 각도 함수를 직접 줄 때 (t ms → 무릎 내각). 주면 reps 대신 이걸 쓴다.
    angle_fn: Callable[[int], float] | None = None
    duration_ms: int | None = None  # angle_fn을 쓸 때 세션 길이
    liveness: LivenessChallenge | None = None
    session_id: str = "synth-1"
    catalog_version: str = "cat_2026-11-01"


def rep_windows(cfg: SynthConfig) -> list[tuple[int, int, int]]:
    """각 렙의 (시작, 최저점, 끝) 시각(ms)."""
    out: list[tuple[int, int, int]] = []
    t = cfg.lead_in_ms
    for r in cfg.reps:
        out.append((t, t + round(r.duration_ms * r.descent_frac), t + r.duration_ms))
        t += r.duration_ms + r.rest_ms
    return out


def total_ms(cfg: SynthConfig) -> int:
    if cfg.angle_fn is not None:
        assert cfg.duration_ms is not None
        return cfg.duration_ms
    return cfg.lead_in_ms + sum(r.duration_ms + r.rest_ms for r in cfg.reps) + cfg.tail_ms


def knee_angle_at(cfg: SynthConfig, t: int) -> float:
    """시각 t(ms)의 목표 무릎 내각(도). 코사인 곡선으로 내려갔다 올라온다."""
    if cfg.angle_fn is not None:
        return cfg.angle_fn(t)
    for (start, bottom, end), r in zip(rep_windows(cfg), cfg.reps, strict=True):
        if start <= t < end:
            depth = STAND_ANGLE - r.bottom_angle
            if t < bottom:
                u = (t - start) / max(1, bottom - start)
            else:
                u = 1.0 - (t - bottom) / max(1, end - bottom)
            return STAND_ANGLE - depth * (1.0 - math.cos(math.pi * u)) / 2.0
    return STAND_ANGLE


Vec3 = tuple[float, float, float]


def pose_3d(knee_angle: float, hands: Hand | None, torso_scale: float = 1.0) -> dict[Joint, Vec3]:
    """무릎 내각 → 3D 관절 (X 좌우: 왼쪽 −, Y 위, Z 앞)."""
    flex = math.radians(180.0 - knee_angle)
    shin_tilt = SHIN_SHARE * flex
    thigh_tilt = (1.0 - SHIN_SHARE) * flex
    lean = LEAN_SHARE * flex
    out: dict[Joint, Vec3] = {}
    for sign, (hip_j, knee_j, ankle_j, sh_j, el_j, wr_j) in (
        (
            -1.0,
            (
                Joint.LEFT_HIP,
                Joint.LEFT_KNEE,
                Joint.LEFT_ANKLE,
                Joint.LEFT_SHOULDER,
                Joint.LEFT_ELBOW,
                Joint.LEFT_WRIST,
            ),
        ),
        (
            1.0,
            (
                Joint.RIGHT_HIP,
                Joint.RIGHT_KNEE,
                Joint.RIGHT_ANKLE,
                Joint.RIGHT_SHOULDER,
                Joint.RIGHT_ELBOW,
                Joint.RIGHT_WRIST,
            ),
        ),
    ):
        ankle = (sign * HIP_HALF, 0.0, 0.0)
        knee = (
            sign * (HIP_HALF + KNEE_SPLAY * math.sin(flex)),
            SHIN * math.cos(shin_tilt),
            SHIN * math.sin(shin_tilt),
        )
        hip = (
            sign * HIP_HALF,
            knee[1] + THIGH * math.cos(thigh_tilt),
            knee[2] - THIGH * math.sin(thigh_tilt),
        )
        torso = TORSO * torso_scale
        shoulder = (
            sign * SHOULDER_HALF,
            hip[1] + torso * math.cos(lean),
            hip[2] + torso * math.sin(lean),
        )
        raised = (
            hands == "BOTH" or (hands == "LEFT" and sign < 0) or (hands == "RIGHT" and sign > 0)
        )
        direction = 1.0 if raised else -1.0
        elbow = (shoulder[0], shoulder[1] + direction * UPPER_ARM, shoulder[2])
        wrist = (shoulder[0], elbow[1] + direction * FOREARM, shoulder[2])
        out.update(
            {ankle_j: ankle, knee_j: knee, hip_j: hip, sh_j: shoulder, el_j: elbow, wr_j: wrist}
        )
    return out


def _project(p: Vec3, cfg: SynthConfig) -> tuple[float, float]:
    """3D → 정규화 이미지 좌표."""
    scale = 0.5 * cfg.image_height
    ground = 0.92 * cfg.image_height
    u = p[0] if cfg.view == "front" else p[2] + SIDE_DEPTH_OFFSET * math.copysign(1.0, p[0])
    x_px = 0.5 * cfg.image_width + u * scale
    y_px = ground - p[1] * scale
    return x_px / cfg.image_width, y_px / cfg.image_height


def _in(ranges: list[tuple[int, int]], t: int) -> bool:
    return any(a <= t < b for a, b in ranges)


def synth_frames(cfg: SynthConfig) -> list[Frame]:
    """설정대로 모델 원본 형식 프레임 목록을 만든다."""
    rng = random.Random(cfg.seed)
    n = MEDIAPIPE_NUM_LANDMARKS if cfg.model == "mediapipe" else MOVENET_NUM_LANDMARKS
    index = MEDIAPIPE_INDEX if cfg.model == "mediapipe" else MOVENET_INDEX
    face = MEDIAPIPE_FACE_INDICES if cfg.model == "mediapipe" else MOVENET_FACE_INDICES
    frames: list[Frame] = []
    prev: list[Landmark | None] | None = None
    end = total_ms(cfg)
    i = 0
    while True:
        t = round(i * 1000 / cfg.fps)
        if t >= end:
            break
        i += 1
        if _in(cfg.invalid_ranges, t):
            frames.append(Frame(t=t, landmarks=None))
            continue
        if prev is not None and _in(cfg.frozen_ranges, t):
            frames.append(Frame(t=t, landmarks=prev))
            continue
        hands = next((h for a, b, h in cfg.hand_raises if a <= t < b), None)
        scale = 1.0
        if cfg.torso_scale_from is not None and t >= cfg.torso_scale_from[0]:
            scale = cfg.torso_scale_from[1]
        pose = pose_3d(knee_angle_at(cfg, t), hands, scale)
        common: dict[Joint, tuple[float, float]] = {}
        for j, p in pose.items():
            x, y = _project(p, cfg)
            x += rng.gauss(0.0, cfg.noise_px) / cfg.image_width if cfg.noise_px else 0.0
            y += rng.gauss(0.0, cfg.noise_px) / cfg.image_height if cfg.noise_px else 0.0
            common[j] = (x, y)
        if cfg.mirrored:  # 클라이언트가 미러링한 화면 좌표를 그대로 보냈다고 가정
            common = {MIRROR_OF[j]: (1.0 - x, y) for j, (x, y) in common.items()}
        lms: list[Landmark | None] = [None] * n
        for j, (x, y) in common.items():
            lms[index[j]] = Landmark(
                x=x, y=y, z=0.0 if cfg.model == "mediapipe" else None, visibility=cfg.visibility
            )
        if cfg.model == "mediapipe":  # 손가락(17~22)·발(29~32)은 손목·발목 근처로 채움
            for k in range(17, 23):
                lms[k] = lms[index[Joint.LEFT_WRIST] if k % 2 else index[Joint.RIGHT_WRIST]]
            for k in range(29, 33):
                lms[k] = lms[index[Joint.LEFT_ANKLE] if k % 2 else index[Joint.RIGHT_ANKLE]]
        for k in face:
            lms[k] = None
        frames.append(Frame(t=t, landmarks=lms))
        prev = lms
    return frames


def synth_meta(cfg: SynthConfig) -> SessionMeta:
    return SessionMeta(
        session_id=cfg.session_id,
        exercise_type="SQUAT",
        catalog_version=cfg.catalog_version,
        fps=cfg.fps,
        image_width=cfg.image_width,
        image_height=cfg.image_height,
        mirrored=cfg.mirrored,
        device=Device(platform=Platform.ANDROID, model_version=MODEL_VERSIONS[cfg.model]),
        liveness=cfg.liveness,
    )


def synth_session(
    cfg: SynthConfig, frames_per_chunk: int | None = None
) -> tuple[SessionMeta, list[Chunk]]:
    """메타 + 청크 목록."""
    frames = synth_frames(cfg)
    k = frames_per_chunk or CHUNK_FRAMES[cfg.model]
    chunks = [
        Chunk(session_id=cfg.session_id, seq=s, frames=frames[i : i + k])
        for s, i in enumerate(range(0, len(frames), k))
    ]
    return synth_meta(cfg), chunks


def challenge(action: LivenessAction, issued: int, expires: int) -> LivenessChallenge:
    return LivenessChallenge(
        challenge_id="ch-1", action=action, issued_at_t=issued, expires_at_t=expires
    )


def squats(n: int, **kw: object) -> list[RepSpec]:
    """같은 렙 n개."""
    return [RepSpec(**kw) for _ in range(n)]  # type: ignore[arg-type]


def varied_squats(n: int, seed: int = 0, **kw: object) -> list[RepSpec]:
    """사람처럼 렙 시간·깊이·휴식이 조금씩 다른 정상 렙 n개."""
    rng = random.Random(seed)
    return [
        RepSpec(
            bottom_angle=rng.uniform(75, 92),
            duration_ms=rng.randint(1700, 2600),
            rest_ms=rng.randint(500, 1200),
            **kw,  # type: ignore[arg-type]
        )
        for _ in range(n)
    ]
