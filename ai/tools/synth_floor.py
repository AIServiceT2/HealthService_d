"""합성 푸시업·윗몸 일으키기 세션 생성기 (테스트용). 실측 데이터가 아니다.

측면 촬영을 2D로 직접 만든다 (가로 u: 머리 쪽 −, 발 쪽 +, 세로 v: 위 +, 단위 = 몸 길이).
판정 각도를 시간에 따라 바꿔 관절을 기하학적으로 계산한다. 좌우 관절은 같은 자세에
작은 가로 오프셋만 다르다. 무작위 동작 확인(손 들기)은 만들지 않는다.

- 푸시업: 손목은 바닥, 어깨는 손목 바로 위. 팔꿈치 내각 θ로 어깨 높이가 정해지고
  몸(어깨–엉덩이–무릎–발목)은 발목을 바닥에 둔 직선이다. `hip_sag`만큼 엉덩이를 내린다.
- 윗몸 일으키기: 엉덩이·발목은 바닥, 허벅지는 `thigh_tilt_deg`(기본 45°, 무릎 90°)로 세움.
  판정 각도 = 상체 각도(어깨–엉덩이–발목 내각) a면 상체가 바닥에서 (180 − a)° 들린다.
  엉덩이 각도 = 180 − 허벅지 기울기 − 상체가 들린 각도. `thigh_raise_deg`를 주면 렙마다 허벅지를
  그만큼 더 들어 올린다 (무릎을 가슴 쪽으로 당기는 동작 흉내).

출력은 모델 원본 형식(MediaPipe 33 / MoveNet 17)이며 얼굴 인덱스는 null이다.
"""

from __future__ import annotations

import math
import random
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
from rep_engine.schemas import Chunk, Device, Frame, Landmark, Platform, SessionMeta
from tools.synth import CHUNK_FRAMES, FOREARM, MODEL_VERSIONS, SHIN, THIGH, TORSO, UPPER_ARM, Model

FloorExercise = Literal["PUSHUP", "SITUP"]
Vec2 = tuple[float, float]

#: 쉬는 자세의 판정 각도 (푸시업: 팔을 편 팔꿈치, 윗몸 일으키기: 누운 상체)
REST_ANGLE: dict[FloorExercise, float] = {"PUSHUP": 172.0, "SITUP": 177.0}
SIDE_OFFSET = 0.03  # 좌우 관절을 구분하는 작은 화면 오프셋


@dataclass
class FloorRep:
    """렙 1개: 최저 판정 각도(도), 렙 시간(ms), 렙 뒤 휴식(ms)."""

    bottom_angle: float
    duration_ms: int = 1600
    rest_ms: int = 600


@dataclass
class FloorSynthConfig:
    exercise: FloorExercise
    reps: list[FloorRep] = field(default_factory=list)
    fps: int = 15
    image_width: int = 720
    image_height: int = 1280
    #: 화면 세로 대비 몸 길이 비율 (누운 몸이 세로 화면 가로에 들어가게 작게)
    person_scale: float = 0.3
    model: Model = "mediapipe"
    mirrored: bool = False
    noise_px: float = 0.0
    seed: int = 0
    lead_in_ms: int = 1500
    tail_ms: int = 1000
    visibility: float = 0.9
    #: 푸시업: 엉덩이를 몸통 직선에서 아래로 내리는 양 (몸 길이 단위)
    hip_sag: float = 0.0
    #: 윗몸 일으키기: 허벅지 기울기(도, 바닥 기준). 작을수록 다리를 편 것
    thigh_tilt_deg: float = 45.0
    #: 윗몸 일으키기: 렙 최저점에서 허벅지를 더 들어 올리는 양(도)
    thigh_raise_deg: float = 0.0
    #: [start, end) ms 동안 사람 미검출 (landmarks=null)
    invalid_ranges: list[tuple[int, int]] = field(default_factory=list)
    session_id: str = "synth-floor-1"
    catalog_version: str = "cat_2026-11-10"


def total_ms(cfg: FloorSynthConfig) -> int:
    return cfg.lead_in_ms + sum(r.duration_ms + r.rest_ms for r in cfg.reps) + cfg.tail_ms


def rep_windows(cfg: FloorSynthConfig) -> list[tuple[int, int, int]]:
    """각 렙의 (시작, 최저점, 끝) 시각(ms). 최저점은 렙 시간의 절반."""
    out: list[tuple[int, int, int]] = []
    t = cfg.lead_in_ms
    for r in cfg.reps:
        out.append((t, t + r.duration_ms // 2, t + r.duration_ms))
        t += r.duration_ms + r.rest_ms
    return out


def progress_at(cfg: FloorSynthConfig, t: int) -> tuple[float, float]:
    """(시각 t의 진행도 0~1, 그 렙의 최저 각도). 코사인 곡선으로 굽혔다 편다.

    렙 밖이면 (0, 쉬는 각도).
    """
    for (start, bottom, end), r in zip(rep_windows(cfg), cfg.reps, strict=True):
        if start <= t < end:
            u = (
                (t - start) / (bottom - start)
                if t < bottom
                else 1.0 - (t - bottom) / (end - bottom)
            )
            return (1.0 - math.cos(math.pi * u)) / 2.0, r.bottom_angle
    return 0.0, REST_ANGLE[cfg.exercise]


def angle_at(cfg: FloorSynthConfig, t: int) -> float:
    """시각 t(ms)의 목표 판정 각도(도)."""
    rest = REST_ANGLE[cfg.exercise]
    e, bottom = progress_at(cfg, t)
    return rest - (rest - bottom) * e


def _lerp(a: Vec2, b: Vec2, s: float) -> Vec2:
    return (a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)


def pushup_pose(elbow_angle: float, hip_sag: float) -> dict[str, Vec2]:
    """팔꿈치 내각 → 한쪽 관절 (어깨, 팔꿈치, 손목, 엉덩이, 무릎, 발목)."""
    th = math.radians(elbow_angle)
    h = math.sqrt(UPPER_ARM**2 + FOREARM**2 - 2 * UPPER_ARM * FOREARM * math.cos(th))
    wrist = (0.0, 0.0)
    shoulder = (0.0, h)
    # 손목에서 본 팔꿈치 방향 (위에서 발 쪽으로 alpha만큼)
    alpha = math.acos((FOREARM**2 + h**2 - UPPER_ARM**2) / (2 * FOREARM * h))
    elbow = (FOREARM * math.sin(alpha), FOREARM * math.cos(alpha))
    body = TORSO + THIGH + SHIN
    ankle = (math.sqrt(body**2 - h**2), 0.0)
    hip = _lerp(shoulder, ankle, TORSO / body)
    hip = (hip[0], hip[1] - hip_sag)
    knee = _lerp(hip, ankle, THIGH / (THIGH + SHIN))
    return {"sh": shoulder, "el": elbow, "wr": wrist, "hip": hip, "knee": knee, "ank": ankle}


def situp_pose(torso_angle: float, thigh_tilt_deg: float) -> dict[str, Vec2]:
    """상체 각도(어깨–엉덩이–발목 내각) → 한쪽 관절. 팔은 가슴 앞에 모은다."""
    tilt = math.radians(thigh_tilt_deg)
    hip = (0.0, 0.0)
    knee = (THIGH * math.cos(tilt), THIGH * math.sin(tilt))
    ankle = (knee[0] + math.sqrt(SHIN**2 - knee[1] ** 2), 0.0)
    phi = math.radians(180.0 - torso_angle)  # 상체가 바닥(엉덩이–발목 선)에서 들린 각도
    shoulder = (-TORSO * math.cos(phi), TORSO * math.sin(phi))
    elbow = _lerp(shoulder, hip, UPPER_ARM / TORSO)
    wrist = _lerp(shoulder, hip, 0.2)
    return {"sh": shoulder, "el": elbow, "wr": wrist, "hip": hip, "knee": knee, "ank": ankle}


_SIDE_JOINTS: dict[str, tuple[Joint, Joint]] = {
    "sh": (Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER),
    "el": (Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW),
    "wr": (Joint.LEFT_WRIST, Joint.RIGHT_WRIST),
    "hip": (Joint.LEFT_HIP, Joint.RIGHT_HIP),
    "knee": (Joint.LEFT_KNEE, Joint.RIGHT_KNEE),
    "ank": (Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE),
}


def _common(cfg: FloorSynthConfig, t: int) -> dict[Joint, Vec2]:
    """시각 t → 공통 골격 정규화 좌표 (얼굴 제외)."""
    angle = angle_at(cfg, t)
    if cfg.exercise == "PUSHUP":
        pose = pushup_pose(angle, cfg.hip_sag)
    else:
        e, _ = progress_at(cfg, t)
        pose = situp_pose(angle, cfg.thigh_tilt_deg + cfg.thigh_raise_deg * e)
    scale = cfg.person_scale * cfg.image_height
    x0 = (0.2 if cfg.exercise == "PUSHUP" else 0.45) * cfg.image_width
    ground = 0.7 * cfg.image_height
    out: dict[Joint, Vec2] = {}
    for key, (left, right) in _SIDE_JOINTS.items():
        u, v = pose[key]
        for j, off in ((left, -SIDE_OFFSET), (right, SIDE_OFFSET)):
            out[j] = (
                (x0 + (u + off) * scale) / cfg.image_width,
                (ground - v * scale) / cfg.image_height,
            )
    return out


def synth_frames(cfg: FloorSynthConfig) -> list[Frame]:
    """설정대로 모델 원본 형식 프레임 목록을 만든다."""
    rng = random.Random(cfg.seed)
    mp = cfg.model == "mediapipe"
    n = MEDIAPIPE_NUM_LANDMARKS if mp else MOVENET_NUM_LANDMARKS
    index = MEDIAPIPE_INDEX if mp else MOVENET_INDEX
    face = MEDIAPIPE_FACE_INDICES if mp else MOVENET_FACE_INDICES
    frames: list[Frame] = []
    end = total_ms(cfg)
    i = 0
    while (t := round(i * 1000 / cfg.fps)) < end:
        i += 1
        if any(a <= t < b for a, b in cfg.invalid_ranges):
            frames.append(Frame(t=t, landmarks=None))
            continue
        common = _common(cfg, t)
        if cfg.noise_px:
            common = {
                j: (
                    x + rng.gauss(0.0, cfg.noise_px) / cfg.image_width,
                    y + rng.gauss(0.0, cfg.noise_px) / cfg.image_height,
                )
                for j, (x, y) in common.items()
            }
        if cfg.mirrored:  # 클라이언트가 미러링한 화면 좌표를 그대로 보냈다고 가정
            common = {MIRROR_OF[j]: (1.0 - x, y) for j, (x, y) in common.items()}
        lms: list[Landmark | None] = [None] * n
        for j, (x, y) in common.items():
            lms[index[j]] = Landmark(x=x, y=y, z=0.0 if mp else None, visibility=cfg.visibility)
        if mp:  # 손가락(17~22)·발(29~32)은 손목·발목 자리로 채움
            for k in range(17, 23):
                lms[k] = lms[index[Joint.LEFT_WRIST] if k % 2 else index[Joint.RIGHT_WRIST]]
            for k in range(29, 33):
                lms[k] = lms[index[Joint.LEFT_ANKLE] if k % 2 else index[Joint.RIGHT_ANKLE]]
        for k in face:
            lms[k] = None
        frames.append(Frame(t=t, landmarks=lms))
    return frames


def synth_meta(cfg: FloorSynthConfig) -> SessionMeta:
    return SessionMeta(
        session_id=cfg.session_id,
        exercise_type=cfg.exercise,
        catalog_version=cfg.catalog_version,
        fps=cfg.fps,
        image_width=cfg.image_width,
        image_height=cfg.image_height,
        mirrored=cfg.mirrored,
        device=Device(platform=Platform.ANDROID, model_version=MODEL_VERSIONS[cfg.model]),
        liveness=None,
    )


def synth_session(cfg: FloorSynthConfig) -> tuple[SessionMeta, list[Chunk]]:
    """메타 + 청크 목록."""
    frames = synth_frames(cfg)
    k = CHUNK_FRAMES[cfg.model]
    chunks = [
        Chunk(session_id=cfg.session_id, seq=s, frames=frames[i : i + k])
        for s, i in enumerate(range(0, len(frames), k))
    ]
    return synth_meta(cfg), chunks


def reps(n: int, bottom_angle: float, **kw: int) -> list[FloorRep]:
    """같은 렙 n개."""
    return [FloorRep(bottom_angle=bottom_angle, **kw) for _ in range(n)]
