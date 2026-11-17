"""합성 런지·인버티드 숄더 프레스·글루트 브릿지 세션 생성기 (테스트용). 실측 데이터가 아니다.

`synth_floor.py`와 같은 방식: 측면 촬영을 2D로 직접 만든다 (가로 u: 머리·뒤쪽 −, 앞·발 쪽 +,
세로 v: 위 +, 단위 = 몸 길이). 판정 각도를 시간에 따라 바꿔 관절을 기하학적으로 계산한다.
무작위 동작 확인(손 들기)은 만들지 않는다.

- 런지(`LUNGE`): 판정 각도 = 무릎 내각 θ. 왼다리가 앞(정강이 수직, 허벅지가 θ만큼 굽음), 오른다리가
  뒤(허벅지 수직, 정강이가 뒤로). 그래서 두 무릎 각도는 모두 θ, 좌우 엉덩이 각도 차는 180 − θ.
  `stance="squat"`이면 두 다리를 같게(앞다리 모양) 만들어 무릎만 굽힌 스쿼트처럼 보이게 한다
  (엉덩이 각도 차 0).
- 인버티드 숄더 프레스(`INVERTED_SHOULDER_PRESS`): 손목은 바닥, 어깨는 손목 바로 위. 팔꿈치 내각 θ로
  어깨 높이가 정해지고(`synth_floor.pushup_pose`와 같은 팔), 엉덩이는 어깨–엉덩이–발목 내각이
  `pike_hip_deg`가 되도록 접힌다. 다리는 편다. `pike_hip_deg`를 178로 주면 일반 푸시업 자세.
- 사이드 레그 리프트(`SIDE_LEG_LIFT`): 판정 각도 = 180 − 다리 벌림. 옆으로 누운 몸을 앞(배 쪽)에서
  본다. 몸은 화면 가로로 눕고, 아래(오른쪽) 다리는 바닥에 수평, 위(왼쪽) 다리는 위쪽 엉덩이에서
  벌림 각도만큼 위로 든다. `stance="squat"`은 쓰지 않는다.
- 글루트 브릿지(`GLUTE_BRIDGE`): 판정 각도 u = 180 − 엉덩이 내각(어깨–엉덩이–무릎). 어깨는 바닥에
  두고, 엉덩이 내각이 커질수록 상체가 바닥에서 들린다(가정: 내각 135°에서 0°, 1° 커질 때 0.5°).
  발목은 바닥.

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
from tools.synth_floor import FloorRep, pushup_pose

MoreExercise = Literal["LUNGE", "INVERTED_SHOULDER_PRESS", "GLUTE_BRIDGE", "SIDE_LEG_LIFT"]
Vec2 = tuple[float, float]

#: 쉬는 자세의 판정 각도 (런지: 선 무릎, 숄더 프레스: 편 팔꿈치, 브릿지: 누운 엉덩이 굽힘)
REST_ANGLE: dict[MoreExercise, float] = {
    "LUNGE": 175.0,
    "INVERTED_SHOULDER_PRESS": 172.0,
    "GLUTE_BRIDGE": 45.0,
    "SIDE_LEG_LIFT": 177.0,
}
#: 화면 배치 (가로 기준점 비율, 바닥 높이 비율, 화면 세로 대비 몸 길이 비율)
_LAYOUT: dict[MoreExercise, tuple[float, float, float]] = {
    "LUNGE": (0.5, 0.85, 0.45),
    "INVERTED_SHOULDER_PRESS": (0.25, 0.7, 0.3),
    "GLUTE_BRIDGE": (0.3, 0.7, 0.3),
    "SIDE_LEG_LIFT": (0.45, 0.6, 0.3),
}
SIDE_OFFSET = 0.03  # 좌우 관절을 구분하는 작은 화면 오프셋
LUNGE_FRONT_FOOT = 0.35  # 런지 앞발 위치 (몸 길이 단위)
BRIDGE_REST_HIP = 135.0  # 브릿지: 상체가 바닥에 붙어 있는 엉덩이 내각
BRIDGE_TORSO_GAIN = 0.5  # 브릿지: 엉덩이 내각 1°당 상체가 들리는 각도
SIDE_HIP_W = 0.18  # 사이드 레그 리프트: 옆으로 누웠을 때 위·아래 엉덩이 높이 차 (몸 길이 단위)
SIDE_SHOULDER_W = 0.22  # 위·아래 어깨 높이 차


@dataclass
class MoreSynthConfig:
    exercise: MoreExercise
    reps: list[FloorRep] = field(default_factory=list)
    fps: int = 15
    image_width: int = 720
    image_height: int = 1280
    model: Model = "mediapipe"
    mirrored: bool = False
    noise_px: float = 0.0
    seed: int = 0
    lead_in_ms: int = 1500
    tail_ms: int = 1000
    visibility: float = 0.9
    #: 런지: "lunge"(앞뒤 다리) / "squat"(두 다리 같게, 스쿼트 흉내)
    stance: Literal["lunge", "squat"] = "lunge"
    #: 숄더 프레스: 어깨–엉덩이–발목 내각 (도). 178이면 일반 푸시업 자세
    pike_hip_deg: float = 95.0
    #: 렙 사이(쉬는 시간)마다 몸 전체를 이만큼 띄운다 (몸 길이 단위, 점프 흉내, D-79). 0이면 안 뜀
    jump_height: float = 0.0
    #: 이 관절들의 가시도를 0으로 (예: 런지 뒷다리가 가려짐)
    hidden: frozenset[Joint] = frozenset()
    #: [start, end) ms 동안 사람 미검출 (landmarks=null)
    invalid_ranges: list[tuple[int, int]] = field(default_factory=list)
    session_id: str = "synth-more-1"
    catalog_version: str = "cat_2026-11-17"


def total_ms(cfg: MoreSynthConfig) -> int:
    return cfg.lead_in_ms + sum(r.duration_ms + r.rest_ms for r in cfg.reps) + cfg.tail_ms


def rep_windows(cfg: MoreSynthConfig) -> list[tuple[int, int, int]]:
    """각 렙의 (시작, 최저점, 끝) 시각(ms). 최저점은 렙 시간의 절반."""
    out: list[tuple[int, int, int]] = []
    t = cfg.lead_in_ms
    for r in cfg.reps:
        out.append((t, t + r.duration_ms // 2, t + r.duration_ms))
        t += r.duration_ms + r.rest_ms
    return out


def angle_at(cfg: MoreSynthConfig, t: int) -> float:
    """시각 t(ms)의 목표 판정 각도(도). 코사인 곡선으로 굽혔다 편다."""
    rest = REST_ANGLE[cfg.exercise]
    for (start, bottom, end), r in zip(rep_windows(cfg), cfg.reps, strict=True):
        if start <= t < end:
            u = (
                (t - start) / (bottom - start)
                if t < bottom
                else 1.0 - (t - bottom) / (end - bottom)
            )
            e = (1.0 - math.cos(math.pi * u)) / 2.0
            return rest - (rest - r.bottom_angle) * e
    return rest


def _lerp(a: Vec2, b: Vec2, s: float) -> Vec2:
    return (a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)


def _add(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


Pose = dict[Joint, Vec2]


def _both(pose: Pose, key: tuple[Joint, Joint], p: Vec2) -> None:
    """좌우 같은 자리(작은 오프셋만 다름)."""
    pose[key[0]] = (p[0] - SIDE_OFFSET, p[1])
    pose[key[1]] = (p[0] + SIDE_OFFSET, p[1])


_SH = (Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER)
_EL = (Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW)
_WR = (Joint.LEFT_WRIST, Joint.RIGHT_WRIST)
_HIP = (Joint.LEFT_HIP, Joint.RIGHT_HIP)
_KNEE = (Joint.LEFT_KNEE, Joint.RIGHT_KNEE)
_ANK = (Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE)


def lunge_pose(knee_angle: float, stance: Literal["lunge", "squat"]) -> Pose:
    """무릎 내각 θ → 공통 골격 (왼다리 앞, 오른다리 뒤)."""
    th = math.radians(knee_angle)
    ankle_f = (LUNGE_FRONT_FOOT, 0.0)
    knee_f = (LUNGE_FRONT_FOOT, SHIN)
    hip = _add(knee_f, (-THIGH * math.sin(th), -THIGH * math.cos(th)))
    shoulder = _add(hip, (0.0, TORSO))
    pose: Pose = {}
    _both(pose, _SH, shoulder)
    _both(pose, _EL, _add(shoulder, (0.0, -UPPER_ARM)))
    _both(pose, _WR, _add(shoulder, (0.0, -UPPER_ARM - FOREARM)))
    _both(pose, _HIP, hip)
    pose[Joint.LEFT_KNEE] = (knee_f[0] - SIDE_OFFSET, knee_f[1])
    pose[Joint.LEFT_ANKLE] = (ankle_f[0] - SIDE_OFFSET, ankle_f[1])
    if stance == "squat":
        pose[Joint.RIGHT_KNEE] = (knee_f[0] + SIDE_OFFSET, knee_f[1])
        pose[Joint.RIGHT_ANKLE] = (ankle_f[0] + SIDE_OFFSET, ankle_f[1])
    else:
        knee_b = _add(hip, (0.0, -THIGH))
        ankle_b = _add(knee_b, (-SHIN * math.sin(th), SHIN * math.cos(th)))
        pose[Joint.RIGHT_KNEE] = (knee_b[0] + SIDE_OFFSET, knee_b[1])
        pose[Joint.RIGHT_ANKLE] = (ankle_b[0] + SIDE_OFFSET, ankle_b[1])
    return pose


def shoulder_press_pose(elbow_angle: float, pike_hip_deg: float) -> Pose:
    """팔꿈치 내각 θ, 엉덩이 내각(어깨–엉덩이–발목) φ → 공통 골격 (다리는 편다)."""
    arm = pushup_pose(elbow_angle, 0.0)
    shoulder, elbow, wrist = arm["sh"], arm["el"], arm["wr"]
    leg = THIGH + SHIN
    h = shoulder[1]
    phi = math.radians(pike_hip_deg)
    dist = math.sqrt(TORSO**2 + leg**2 - 2 * TORSO * leg * math.cos(phi))
    ankle = (math.sqrt(dist**2 - h**2), 0.0)
    # 어깨(반지름 TORSO)와 발목(반지름 leg) 두 원의 교점 중 위쪽이 엉덩이
    ex = ((ankle[0] - shoulder[0]) / dist, (ankle[1] - shoulder[1]) / dist)
    along = (TORSO**2 - leg**2 + dist**2) / (2 * dist)
    perp = math.sqrt(max(0.0, TORSO**2 - along**2))
    normal = (-ex[1], ex[0]) if ex[0] >= 0 else (ex[1], -ex[0])
    hip = (
        shoulder[0] + along * ex[0] + perp * normal[0],
        shoulder[1] + along * ex[1] + perp * normal[1],
    )
    pose: Pose = {}
    _both(pose, _SH, shoulder)
    _both(pose, _EL, elbow)
    _both(pose, _WR, wrist)
    _both(pose, _HIP, hip)
    _both(pose, _KNEE, _lerp(hip, ankle, THIGH / leg))
    _both(pose, _ANK, ankle)
    return pose


def bridge_pose(hip_flexion: float) -> Pose:
    """판정 각도 u = 180 − 엉덩이 내각 → 공통 골격 (어깨·발목은 바닥, 팔은 바닥에 둠)."""
    alpha = 180.0 - hip_flexion
    psi = math.radians(max(0.0, (alpha - BRIDGE_REST_HIP) * BRIDGE_TORSO_GAIN))
    shoulder = (0.0, 0.0)
    hip = (TORSO * math.cos(psi), TORSO * math.sin(psi))
    gamma = psi + math.pi - math.radians(alpha)  # 엉덩이→무릎 방향
    knee = _add(hip, (THIGH * math.cos(gamma), THIGH * math.sin(gamma)))
    if knee[1] <= SHIN:
        ankle = (knee[0] + math.sqrt(SHIN**2 - knee[1] ** 2), 0.0)
    else:  # pragma: no cover  (기본 범위에서는 무릎이 정강이보다 높지 않음)
        ankle = (knee[0], knee[1] - SHIN)
    pose: Pose = {}
    _both(pose, _SH, shoulder)
    _both(pose, _EL, (UPPER_ARM, 0.0))
    _both(pose, _WR, (UPPER_ARM + FOREARM, 0.0))
    _both(pose, _HIP, hip)
    _both(pose, _KNEE, knee)
    _both(pose, _ANK, ankle)
    return pose


def side_leg_lift_pose(judge_angle: float) -> Pose:
    """판정 각도 u = 180 − 다리 벌림 → 공통 골격 (왼쪽이 위, 오른쪽이 바닥 쪽)."""
    spread = math.radians(180.0 - judge_angle)
    leg = THIGH + SHIN
    hip_b, hip_t = (0.0, 0.0), (0.0, SIDE_HIP_W)
    sh_b, sh_t = (-TORSO, 0.0), (-TORSO, SIDE_SHOULDER_W)
    direction = (math.cos(spread), math.sin(spread))
    return {
        Joint.RIGHT_SHOULDER: sh_b,
        Joint.LEFT_SHOULDER: sh_t,
        Joint.RIGHT_ELBOW: (-TORSO - UPPER_ARM, 0.0),  # 아래팔은 머리 쪽으로 뻗음
        Joint.RIGHT_WRIST: (-TORSO - UPPER_ARM - FOREARM, 0.0),
        Joint.LEFT_ELBOW: _lerp(sh_t, hip_t, 0.6),  # 위팔은 몸 위에 둠
        Joint.LEFT_WRIST: _lerp(sh_t, hip_t, 0.95),
        Joint.RIGHT_HIP: hip_b,
        Joint.LEFT_HIP: hip_t,
        Joint.RIGHT_KNEE: (THIGH, 0.0),
        Joint.RIGHT_ANKLE: (leg, 0.0),
        Joint.LEFT_KNEE: _add(hip_t, (THIGH * direction[0], THIGH * direction[1])),
        Joint.LEFT_ANKLE: _add(hip_t, (leg * direction[0], leg * direction[1])),
    }


def pose_at(cfg: MoreSynthConfig, t: int) -> Pose:
    """시각 t의 공통 골격 (몸 길이 단위 2D)."""
    angle = angle_at(cfg, t)
    if cfg.exercise == "LUNGE":
        return lunge_pose(angle, cfg.stance)
    if cfg.exercise == "INVERTED_SHOULDER_PRESS":
        return shoulder_press_pose(angle, cfg.pike_hip_deg)
    if cfg.exercise == "SIDE_LEG_LIFT":
        return side_leg_lift_pose(angle)
    return bridge_pose(angle)


def jump_offset(cfg: MoreSynthConfig, t: int) -> float:
    """시각 t에 몸이 뜬 높이 (몸 길이 단위). 렙이 끝난 뒤 쉬는 시간 동안 사인 곡선으로 뜬다."""
    if cfg.jump_height <= 0:
        return 0.0
    for (_, _, end), r in zip(rep_windows(cfg), cfg.reps, strict=True):
        if end <= t < end + r.rest_ms:
            return cfg.jump_height * math.sin(math.pi * (t - end) / r.rest_ms)
    return 0.0


def _common(cfg: MoreSynthConfig, t: int) -> dict[Joint, Vec2]:
    """시각 t → 공통 골격 정규화 좌표 (얼굴 제외)."""
    x_ratio, ground_ratio, scale_ratio = _LAYOUT[cfg.exercise]
    scale = scale_ratio * cfg.image_height
    x0 = x_ratio * cfg.image_width
    ground = ground_ratio * cfg.image_height
    lift = jump_offset(cfg, t)
    return {
        j: ((x0 + u * scale) / cfg.image_width, (ground - (v + lift) * scale) / cfg.image_height)
        for j, (u, v) in pose_at(cfg, t).items()
    }


def synth_frames(cfg: MoreSynthConfig) -> list[Frame]:
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
        vis = {j: 0.0 if j in cfg.hidden else cfg.visibility for j in common}
        if cfg.mirrored:  # 클라이언트가 미러링한 화면 좌표를 그대로 보냈다고 가정
            common = {MIRROR_OF[j]: (1.0 - x, y) for j, (x, y) in common.items()}
            vis = {MIRROR_OF[j]: v for j, v in vis.items()}
        lms: list[Landmark | None] = [None] * n
        for j, (x, y) in common.items():
            lms[index[j]] = Landmark(x=x, y=y, z=0.0 if mp else None, visibility=vis[j])
        if mp:  # 손가락(17~22)·발(29~32)은 손목·발목 자리로 채움
            for k in range(17, 23):
                lms[k] = lms[index[Joint.LEFT_WRIST] if k % 2 else index[Joint.RIGHT_WRIST]]
            for k in range(29, 33):
                lms[k] = lms[index[Joint.LEFT_ANKLE] if k % 2 else index[Joint.RIGHT_ANKLE]]
        for k in face:
            lms[k] = None
        frames.append(Frame(t=t, landmarks=lms))
    return frames


def synth_meta(cfg: MoreSynthConfig) -> SessionMeta:
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


def synth_session(cfg: MoreSynthConfig) -> tuple[SessionMeta, list[Chunk]]:
    """메타 + 청크 목록."""
    frames = synth_frames(cfg)
    k = CHUNK_FRAMES[cfg.model]
    chunks = [
        Chunk(session_id=cfg.session_id, seq=s, frames=frames[i : i + k])
        for s, i in enumerate(range(0, len(frames), k))
    ]
    return synth_meta(cfg), chunks
