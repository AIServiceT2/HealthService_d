"""합성 하이 니·마운틴 클라이머·슈퍼맨·돈키 킥 세션 생성기 (테스트용). 실측 데이터가 아니다.

`synth_more.py`와 같은 방식: 측면 촬영을 2D로 직접 만든다 (가로 u: 머리 쪽 −, 발 쪽 +, 선 자세에서는
앞 +, 세로 v: 위 +, 단위 = 몸 길이). 판정 각도를 시간에 따라 바꿔 관절을 기하학적으로 계산한다.
무작위 동작 확인(손 들기)은 만들지 않는다.

- 하이 니(`HIGH_KNEE`): 선 자세. 다리별 엉덩이 내각 θ로 허벅지를 앞으로 들고
  정강이는 수직으로 늘어뜨린다.
- 마운틴 클라이머(`MOUNTAIN_CLIMBER`): 팔을 편 플랭크(손목은 어깨 바로 아래 바닥). 다리별 엉덩이
  내각 θ만큼 허벅지를 몸 아래(머리 쪽)로 당긴다. `arms="side"`면 손을 바닥에서 떼어 몸통 옆에 둔다
  (누워서 무릎 당기기 흉내: 팔 지지 각도가 작아짐).
- 두 종목의 렙 = 왼다리 `leg_ms` 동안 굽혔다 펴고 이어서 오른다리. `legs="both"`면 두 다리를 동시에
  굽히고(스쿼트·웅크리기 흉내), `legs="left_only"`면 왼다리만 움직인다.
- 슈퍼맨(`SUPERMAN`): 엎드림. 몸 활 각도 α(어깨–엉덩이–발목)를 상체·다리가 반씩 나눠 든다. 팔은 머리
  위로 뻗는다. `arms="side"`면 팔을 몸 옆(엉덩이 쪽)에 둔다.
- 돈키 킥(`DONKEY_KICK`): 네발 자세(손목은 어깨 아래, 무릎은 엉덩이 아래). 판정 각도 u = 180 − 왼쪽
  엉덩이 내각. 찬 다리는 무릎을 90° 굽힌 채 허벅지를 뒤로 든다. 오른다리는 받친다.

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

ExtraExercise = Literal["HIGH_KNEE", "MOUNTAIN_CLIMBER", "SUPERMAN", "DONKEY_KICK"]
Vec2 = tuple[float, float]
Pose = dict[Joint, Vec2]

#: 쉬는 자세의 판정 각도 (하이 니·마운틴 클라이머: 다리별 엉덩이 내각, 슈퍼맨: 몸 활 각도,
#: 돈키 킥: 180 − 엉덩이 내각)
REST_ANGLE: dict[ExtraExercise, float] = {
    "HIGH_KNEE": 178.0,
    "MOUNTAIN_CLIMBER": 176.0,
    "SUPERMAN": 179.0,
    "DONKEY_KICK": 90.0,
}
ALTERNATING: frozenset[ExtraExercise] = frozenset({"HIGH_KNEE", "MOUNTAIN_CLIMBER"})
#: 화면 배치 (가로 기준점 비율, 바닥 높이 비율, 화면 세로 대비 몸 길이 비율)
_LAYOUT: dict[ExtraExercise, tuple[float, float, float]] = {
    "HIGH_KNEE": (0.5, 0.85, 0.45),
    "MOUNTAIN_CLIMBER": (0.2, 0.7, 0.3),
    "SUPERMAN": (0.5, 0.7, 0.3),
    "DONKEY_KICK": (0.3, 0.7, 0.3),
}
SIDE_OFFSET = 0.03  # 좌우 관절을 구분하는 작은 화면 오프셋
LEG = THIGH + SHIN
ARM = UPPER_ARM + FOREARM
SUPERMAN_HIP_V = 0.1  # 엎드렸을 때 엉덩이 높이 (몸 두께)
#: 종목별 기본 `leg_ms`: 번갈아 하는 종목은 다리 하나 0.45초, 나머지는 렙 하나 1.6초(= 0.8초 × 2)
DEFAULT_LEG_MS: dict[ExtraExercise, int] = {
    "HIGH_KNEE": 450,
    "MOUNTAIN_CLIMBER": 450,
    "SUPERMAN": 800,
    "DONKEY_KICK": 800,
}


@dataclass
class ExtraRep:
    """렙 1개.

    - 하이 니·마운틴 클라이머: 왼·오른다리 최저 엉덩이 내각, 다리 하나 동작 시간, 렙 뒤 휴식.
    - 슈퍼맨·돈키 킥: `left_angle`만 쓰고(최저 판정 각도), 렙 시간 = `leg_ms` × 2.
    - `leg_ms`를 주지 않으면 종목 기본값(`DEFAULT_LEG_MS`).
    """

    left_angle: float
    right_angle: float | None = None  # None이면 left_angle과 같음
    leg_ms: int | None = None
    rest_ms: int = 300


def reps(n: int, angle: float, **kw: int) -> list[ExtraRep]:
    """같은 렙 n개."""
    return [ExtraRep(left_angle=angle, **kw) for _ in range(n)]


@dataclass
class ExtraSynthConfig:
    exercise: ExtraExercise
    reps: list[ExtraRep] = field(default_factory=list)
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
    #: 하이 니·마운틴 클라이머 다리 움직임: 번갈아 / 동시에 / 왼다리만
    legs: Literal["alternate", "both", "left_only"] = "alternate"
    #: 팔 위치: 기본(마운틴 클라이머·돈키 킥은 바닥 짚기, 슈퍼맨은 머리 위로 뻗기) / 몸 옆
    arms: Literal["default", "side"] = "default"
    #: 이 관절들의 가시도를 0으로
    hidden: frozenset[Joint] = frozenset()
    #: [start, end) ms 동안 사람 미검출 (landmarks=null)
    invalid_ranges: list[tuple[int, int]] = field(default_factory=list)
    session_id: str = "synth-extra-1"
    catalog_version: str = "cat_2026-11-23"


def _leg_ms(cfg: ExtraSynthConfig, r: ExtraRep) -> int:
    return DEFAULT_LEG_MS[cfg.exercise] if r.leg_ms is None else r.leg_ms


def total_ms(cfg: ExtraSynthConfig) -> int:
    body = sum(2 * _leg_ms(cfg, r) + r.rest_ms for r in cfg.reps)
    return cfg.lead_in_ms + body + cfg.tail_ms


def rep_windows(cfg: ExtraSynthConfig) -> list[tuple[int, int, int]]:
    """각 렙의 (시작, 가운데, 끝) 시각(ms). 번갈아 하는 종목은 가운데 = 왼다리 끝·오른다리 시작."""
    out: list[tuple[int, int, int]] = []
    t = cfg.lead_in_ms
    for r in cfg.reps:
        leg = _leg_ms(cfg, r)
        out.append((t, t + leg, t + 2 * leg))
        t += 2 * leg + r.rest_ms
    return out


def _curve(rest: float, bottom: float, t: int, start: int, end: int) -> float | None:
    """[start, end) 동안 rest → bottom → rest 코사인 곡선. 구간 밖이면 None."""
    if not start <= t < end:
        return None
    u = (t - start) / (end - start)
    e = (1.0 - math.cos(2.0 * math.pi * u)) / 2.0
    return rest - (rest - bottom) * e


def angles_at(cfg: ExtraSynthConfig, t: int) -> tuple[float, float]:
    """시각 t의 (왼쪽, 오른쪽) 판정 각도. 한 각도만 쓰는 종목은 두 값이 같다."""
    rest = REST_ANGLE[cfg.exercise]
    for (start, mid, end), r in zip(rep_windows(cfg), cfg.reps, strict=True):
        right_bottom = r.left_angle if r.right_angle is None else r.right_angle
        if cfg.exercise not in ALTERNATING:
            a = _curve(rest, r.left_angle, t, start, end)
            if a is not None:
                return a, a
            continue
        if cfg.legs == "both":
            left = _curve(rest, r.left_angle, t, start, end)
            right = _curve(rest, right_bottom, t, start, end)
        else:
            left = _curve(rest, r.left_angle, t, start, mid)
            right = None if cfg.legs == "left_only" else _curve(rest, right_bottom, t, mid, end)
        if left is not None or right is not None:
            return (rest if left is None else left), (rest if right is None else right)
    return rest, rest


def _add(a: Vec2, b: Vec2, s: float = 1.0) -> Vec2:
    return (a[0] + b[0] * s, a[1] + b[1] * s)


def _lerp(a: Vec2, b: Vec2, s: float) -> Vec2:
    return (a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)


def _unit(a: Vec2, b: Vec2) -> Vec2:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n)


def _rot(v: Vec2, deg: float) -> Vec2:
    """반시계 방향 회전 (도). 음수면 시계 방향."""
    r = math.radians(deg)
    return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r))


def _shift(p: Vec2, side: int) -> Vec2:
    """왼쪽(−1)·오른쪽(+1) 관절을 화면에서 조금 떼어 놓는다."""
    return (p[0] + side * SIDE_OFFSET, p[1])


def _put(pose: Pose, left: Joint, right: Joint, p: Vec2) -> None:
    pose[left] = _shift(p, -1)
    pose[right] = _shift(p, +1)


def high_knee_pose(left_hip: float, right_hip: float) -> Pose:
    """다리별 엉덩이 내각 → 선 자세 공통 골격 (허벅지를 앞(+u)으로 듦, 정강이는 수직)."""
    hip = (0.0, LEG)
    shoulder = (0.0, LEG + TORSO)
    pose: Pose = {}
    _put(pose, Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER, shoulder)
    _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, _add(shoulder, (0.0, -UPPER_ARM)))
    _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, _add(shoulder, (0.0, -ARM)))
    _put(pose, Joint.LEFT_HIP, Joint.RIGHT_HIP, hip)
    for side, theta, kj, aj in (
        (-1, left_hip, Joint.LEFT_KNEE, Joint.LEFT_ANKLE),
        (+1, right_hip, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE),
    ):
        phi = math.radians(180.0 - theta)
        knee = _add(hip, (math.sin(phi), -math.cos(phi)), THIGH)
        pose[kj] = _shift(knee, side)
        pose[aj] = _shift(_add(knee, (0.0, -SHIN)), side)
    return pose


def mountain_climber_pose(left_hip: float, right_hip: float, arms: str) -> Pose:
    """다리별 엉덩이 내각 → 플랭크 공통 골격 (머리 −u, 손목은 어깨 아래 바닥)."""
    shoulder = (0.0, ARM)
    body = TORSO + LEG
    ankle = (math.sqrt(body**2 - ARM**2), 0.0)
    hip = _lerp(shoulder, ankle, TORSO / body)
    back = _unit(hip, ankle)  # 다리를 편 방향
    pose: Pose = {}
    _put(pose, Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER, shoulder)
    if arms == "side":  # 손을 바닥에서 떼어 몸통 옆에 둠
        along = _unit(shoulder, hip)
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, _add(shoulder, along, UPPER_ARM))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, _add(shoulder, along, ARM))
    else:
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, (0.0, FOREARM))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, (0.0, 0.0))
    _put(pose, Joint.LEFT_HIP, Joint.RIGHT_HIP, hip)
    for side, theta, kj, aj in (
        (-1, left_hip, Joint.LEFT_KNEE, Joint.LEFT_ANKLE),
        (+1, right_hip, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE),
    ):
        thigh = _rot(back, -(180.0 - theta))  # 시계 방향 = 몸 아래·머리 쪽
        knee = _add(hip, thigh, THIGH)
        pose[kj] = _shift(knee, side)
        pose[aj] = _shift(_add(knee, back, SHIN), side)
    return pose


def superman_pose(arch: float, arms: str) -> Pose:
    """몸 활 각도 α → 엎드린 공통 골격 (상체·다리가 (180 − α)/2씩 듦, 머리 −u)."""
    a = math.radians((180.0 - arch) / 2.0)
    hip = (0.0, SUPERMAN_HIP_V)
    head_dir = (-math.cos(a), math.sin(a))
    foot_dir = (math.cos(a), math.sin(a))
    shoulder = _add(hip, head_dir, TORSO)
    pose: Pose = {}
    _put(pose, Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER, shoulder)
    if arms == "side":  # 팔을 몸 옆(엉덩이 쪽)에 둠
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, _lerp(shoulder, hip, 0.6))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, _lerp(shoulder, hip, 0.95))
    else:  # 머리 위로 뻗음 (몸통 선을 그대로 이어감)
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, _add(shoulder, head_dir, UPPER_ARM))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, _add(shoulder, head_dir, ARM))
    _put(pose, Joint.LEFT_HIP, Joint.RIGHT_HIP, hip)
    _put(pose, Joint.LEFT_KNEE, Joint.RIGHT_KNEE, _add(hip, foot_dir, THIGH))
    _put(pose, Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE, _add(hip, foot_dir, LEG))
    return pose


def donkey_kick_pose(judge: float, arms: str) -> Pose:
    """판정 각도 u = 180 − 왼쪽 엉덩이 내각 → 네발 자세 공통 골격 (왼다리가 참, 머리 −u)."""
    shoulder = (0.0, ARM)
    hip = (TORSO, THIGH)
    to_shoulder = _unit(hip, shoulder)
    pose: Pose = {}
    _put(pose, Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER, shoulder)
    if arms == "side":
        along = _unit(shoulder, hip)
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, _add(shoulder, along, UPPER_ARM))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, _add(shoulder, along, ARM))
    else:
        _put(pose, Joint.LEFT_ELBOW, Joint.RIGHT_ELBOW, (0.0, FOREARM))
        _put(pose, Joint.LEFT_WRIST, Joint.RIGHT_WRIST, (0.0, 0.0))
    _put(pose, Joint.LEFT_HIP, Joint.RIGHT_HIP, hip)
    rest_hip = 180.0 - REST_ANGLE["DONKEY_KICK"]
    for side, hip_angle, kj, aj in (
        (-1, 180.0 - judge, Joint.LEFT_KNEE, Joint.LEFT_ANKLE),
        (+1, rest_hip, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE),
    ):
        thigh = _rot(to_shoulder, hip_angle)  # 반시계 = 아래 → 뒤 → 위
        knee = _add(hip, thigh, THIGH)
        pose[kj] = _shift(knee, side)
        pose[aj] = _shift(_add(knee, _rot(thigh, 90.0), SHIN), side)  # 무릎 90° 굽힘
    return pose


def pose_at(cfg: ExtraSynthConfig, t: int) -> Pose:
    """시각 t의 공통 골격 (몸 길이 단위 2D)."""
    left, right = angles_at(cfg, t)
    if cfg.exercise == "HIGH_KNEE":
        return high_knee_pose(left, right)
    if cfg.exercise == "MOUNTAIN_CLIMBER":
        return mountain_climber_pose(left, right, cfg.arms)
    if cfg.exercise == "SUPERMAN":
        return superman_pose(left, cfg.arms)
    return donkey_kick_pose(left, cfg.arms)


def _common(cfg: ExtraSynthConfig, t: int) -> dict[Joint, Vec2]:
    """시각 t → 공통 골격 정규화 좌표 (얼굴 제외)."""
    x_ratio, ground_ratio, scale_ratio = _LAYOUT[cfg.exercise]
    scale = scale_ratio * cfg.image_height
    x0 = x_ratio * cfg.image_width
    ground = ground_ratio * cfg.image_height
    return {
        j: ((x0 + u * scale) / cfg.image_width, (ground - v * scale) / cfg.image_height)
        for j, (u, v) in pose_at(cfg, t).items()
    }


def synth_frames(cfg: ExtraSynthConfig) -> list[Frame]:
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


def synth_meta(cfg: ExtraSynthConfig) -> SessionMeta:
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


def synth_session(cfg: ExtraSynthConfig) -> tuple[SessionMeta, list[Chunk]]:
    """메타 + 청크 목록."""
    frames = synth_frames(cfg)
    k = CHUNK_FRAMES[cfg.model]
    chunks = [
        Chunk(session_id=cfg.session_id, seq=s, frames=frames[i : i + k])
        for s, i in enumerate(range(0, len(frames), k))
    ]
    return synth_meta(cfg), chunks
