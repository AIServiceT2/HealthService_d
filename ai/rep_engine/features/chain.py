"""굽혔다 펴는 종목(푸시업·윗몸 일으키기·런지·인버티드 숄더 프레스·글루트 브릿지)의 프레임 특징.

런지·인버티드 숄더 프레스·글루트 브릿지의 사슬은 아래 `*_SPEC` 정의의 주석을 본다 (D-71~D-73).

판정 각도는 관절 3개(가운데가 꼭짓점)의 **내각**이다. 쉬는 자세에서 크고 굽힐수록 작아진다.
- 푸시업: 팔꿈치 각도 = 어깨–팔꿈치–손목. 팔을 펴면 약 180°.
- 윗몸 일으키기: 상체 각도 = 어깨–엉덩이–발목. 엉덩이와 발목이 바닥에 있으므로 엉덩이–발목 선을
  바닥으로 본다. 누우면 약 180°, 상체가 바닥에서 x° 들리면 180 − x. 화면 수평선이 아니라 몸 기준이라
  폰이 기울어도 값이 같다. 무릎만 가슴 쪽으로 당겨서는 거의 변하지 않는다 (D-70).

측면 선택은 스쿼트와 같다: 좌우 사슬 중 관절 3개가 모두 `min_visibility` 이상인 쪽을 쓴다.
두 쪽 → 평균, 한 쪽 → 그쪽만, 없음 → **무효 프레임**.
판정 각도에만 One Euro 필터를 쓴다(D-13과 같음).

둘째 판정 각도(`aux_angle`, 필터 적용)는 인정 조건을 하나 더 거는 종목만 쓴다.
- 윗몸 일으키기: 엉덩이 각도 = 어깨–엉덩이–무릎 (상체를 무릎 쪽으로 충분히 접었는지).

보조 각도(`form_angle`, 필터 전 값)는 종목마다 다르다.
- 푸시업 `body_line_dev`: 180 − (어깨–엉덩이–발목 내각). 몸이 일직선이면 0°.
- 윗몸 일으키기 `knee_angle`: 엉덩이–무릎–발목 내각.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from rep_engine.adapters import Point, SkeletonFrame
from rep_engine.config import FeaturesCfg, TorsoRangeCfg
from rep_engine.features.filters import OneEuroFilter
from rep_engine.features.geometry import angle_deg, distance, tilt_from_vertical_deg
from rep_engine.features.posture import posture_ok, torso_from_up
from rep_engine.landmarks import Joint

Triple = tuple[Joint, Joint, Joint]
Joints = tuple[Point | None, ...]
#: (관절 목록, min_visibility) → 보조 각도(도) 또는 None
FormFn = Callable[[Joints, float], float | None]
#: (관절 목록, min_visibility) → (판정 값, 쓰인 관절 평균 가시도) 또는 None (관절이 안 보임)
JudgeFn = Callable[[Joints, float], tuple[float, float] | None]

FULL_EXTENSION_DEG = 180.0  # 일직선 = 180° (정의상 상수)

LEFT_ARM: Triple = (Joint.LEFT_SHOULDER, Joint.LEFT_ELBOW, Joint.LEFT_WRIST)
RIGHT_ARM: Triple = (Joint.RIGHT_SHOULDER, Joint.RIGHT_ELBOW, Joint.RIGHT_WRIST)
LEFT_TORSO_FLOOR: Triple = (Joint.LEFT_SHOULDER, Joint.LEFT_HIP, Joint.LEFT_ANKLE)
RIGHT_TORSO_FLOOR: Triple = (Joint.RIGHT_SHOULDER, Joint.RIGHT_HIP, Joint.RIGHT_ANKLE)
LEFT_TORSO_THIGH: Triple = (Joint.LEFT_SHOULDER, Joint.LEFT_HIP, Joint.LEFT_KNEE)
RIGHT_TORSO_THIGH: Triple = (Joint.RIGHT_SHOULDER, Joint.RIGHT_HIP, Joint.RIGHT_KNEE)
LEFT_BODY_LINE: Triple = (Joint.LEFT_SHOULDER, Joint.LEFT_HIP, Joint.LEFT_ANKLE)
RIGHT_BODY_LINE: Triple = (Joint.RIGHT_SHOULDER, Joint.RIGHT_HIP, Joint.RIGHT_ANKLE)
LEFT_LEG3: Triple = (Joint.LEFT_HIP, Joint.LEFT_KNEE, Joint.LEFT_ANKLE)
RIGHT_LEG3: Triple = (Joint.RIGHT_HIP, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE)
#: 상체/하체 비율용 (어깨, 엉덩이, 무릎, 발목)
_LEFT_BODY = (Joint.LEFT_SHOULDER, Joint.LEFT_HIP, Joint.LEFT_KNEE, Joint.LEFT_ANKLE)
_RIGHT_BODY = (Joint.RIGHT_SHOULDER, Joint.RIGHT_HIP, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE)


@dataclass(frozen=True, slots=True)
class ChainFeatures:
    """프레임 1개의 특징. `valid=False`면 각도 필드는 모두 None."""

    t: int
    valid: bool
    #: 판정 각도 (필터 적용)
    angle: float | None = None
    angle_raw: float | None = None
    #: 둘째 판정 각도 (필터 적용). 종목에 없거나 관절이 안 보이면 None
    aux_angle: float | None = None
    #: 좌우 판정 각도 차 (필터 전, 양쪽이 모두 보일 때만)
    asymmetry: float | None = None
    #: 종목별 보조 각도 (모듈 설명 참고)
    form_angle: float | None = None
    core_visibility: float | None = None
    #: 상체 길이 ÷ (허벅지+정강이). 사람 교체 탐지(BODY_PROPORTION_SHIFT)용
    torso_leg_ratio: float | None = None
    #: 유지 각도 (필터 전): 렙 내내 일정 이상이어야 하는 각도 (예: 푸시업 무릎, D-78). 없으면 None
    hold_angle: float | None = None
    #: 바닥 쪽 발목 높이 = 보이는 발목 중 화면 y가 가장 큰 값(픽셀, 아래로 증가). 점프 판정용 (D-79)
    floor_y: float | None = None
    #: 보이는 다리의 엉덩이–발목 거리 평균(픽셀). 점프 높이를 몸 크기에 맞춰 나누는 데 쓴다
    leg_length: float | None = None


@dataclass(frozen=True, slots=True)
class ChainSpec:
    """종목의 판정 사슬(좌·우), 보조 각도 계산, 둘째 판정 사슬(없으면 None).

    `invert=True`면 판정 각도 = 180 − 내각이다. 동작할수록 내각이 **커지는** 종목(글루트 브릿지)을
    '쉬는 자세에서 크고 동작할수록 작아지는' 각도로 바꿔 같은 상태 머신을 쓰게 한다 (D-73).

    `pair=True`면 좌우 사슬을 따로 재지 않고, **두 사슬 사이 각도**(왼쪽 첫 관절→끝 관절 선과 오른쪽
    첫 관절→끝 관절 선이 이루는 각)를 판정 각도로 쓴다. 양쪽이 모두 보여야 유효 프레임이다.
    사이드 레그 리프트의 다리 벌림 각도가 쓴다 (D-77).

    `hold`는 렙 내내 일정 각도 이상이어야 하는 사슬(유지 각도, 보이는 쪽 평균)이다. 푸시업의
    무릎(무릎을 대고 하면 무릎이 굽음)이 쓴다 (D-78). 관절 3개 내각이 아닌 유지 값은 `hold_fn`으로
    준다 (마운틴 클라이머·돈키 킥의 팔 지지 각도, D-84·D-86). 둘 다 있으면 `hold`를 쓴다.

    `single=True`면 `left` 사슬 하나만 쓴다 (`right`는 무시). 다리를 번갈아 하는 종목이 다리마다
    추출기를 따로 두는 데 쓴다 (D-83).

    `pick`은 좌우 판정 각도를 합치는 방법이다.
    `"mean"`(기본) = 평균, `"min"` = 작은 쪽(`invert` 뒤).
    한 다리씩 차는 돈키 킥이 `"min"`을 쓴다 (평균이면 찬 다리 각도가 반으로 줄어듦, D-86).
    """

    left: Triple
    right: Triple
    form: FormFn
    aux: tuple[Triple, Triple] | None = None
    invert: bool = False
    pair: bool = False
    hold: tuple[Triple, Triple] | None = None
    hold_fn: FormFn | None = None
    single: bool = False
    pick: Literal["mean", "min"] = "mean"
    #: 관절 3개 내각이 아닌 판정 값을 직접 계산하는 함수. 있으면 `left`·`right`·`pair`는 무시
    #: (버드독: 180 − min(팔 뻗음, 다리 뻗음), D-91)
    judge_fn: JudgeFn | None = None
    #: 관절 3개 내각이 아닌 둘째 판정 값. `aux`가 있으면 `aux`를 쓴다 (사이드 런지 다리 벌림, D-90)
    aux_fn: FormFn | None = None


def _vis(p: Point | None, min_vis: float) -> Point | None:
    return p if p is not None and p.vis >= min_vis else None


def _triple_angle(joints: Joints, tri: Triple, min_vis: float) -> tuple[float, float] | None:
    """(내각, 세 관절 평균 가시도). 하나라도 안 보이면 None."""
    a, b, c = (_vis(joints[j], min_vis) for j in tri)
    if a is None or b is None or c is None:
        return None
    ang = angle_deg((a.x, a.y), (b.x, b.y), (c.x, c.y))
    if ang is None:
        return None
    return ang, (a.vis + b.vis + c.vis) / 3.0


def _pair_angle(joints: Joints, spec: ChainSpec, min_vis: float) -> tuple[float, float] | None:
    """(두 사슬 사이 각도, 쓰인 관절 평균 가시도). 한쪽이라도 안 보이면 None."""
    left = [_vis(joints[j], min_vis) for j in spec.left]
    right = [_vis(joints[j], min_vis) for j in spec.right]
    if any(p is None for p in left) or any(p is None for p in right):
        return None
    l0, l2, r0, r2 = left[0], left[2], right[0], right[2]
    assert l0 is not None and l2 is not None and r0 is not None and r2 is not None
    ang = angle_deg((l2.x - l0.x, l2.y - l0.y), (0.0, 0.0), (r2.x - r0.x, r2.y - r0.y))
    if ang is None:
        return None
    pts = [p for p in (*left, *right) if p is not None]
    return ang, sum(p.vis for p in pts) / len(pts)


def _sides(joints: Joints, spec: ChainSpec, min_vis: float) -> list[tuple[float, float]]:
    """판정 각도 후보 (각도, 가시도). 좌우 사슬 각각, `pair`면 두 사슬 사이 각도 하나."""
    if spec.judge_fn is not None:
        j = spec.judge_fn(joints, min_vis)
        return [] if j is None else [j]
    if spec.pair:
        r = _pair_angle(joints, spec, min_vis)
        return [] if r is None else [r]
    tris = (spec.left,) if spec.single else (spec.left, spec.right)
    return [r for tri in tris if (r := _triple_angle(joints, tri, min_vis))]


def _mean_of_sides(joints: Joints, sides: tuple[Triple, Triple], min_vis: float) -> float | None:
    vals = [r[0] for tri in sides if (r := _triple_angle(joints, tri, min_vis)) is not None]
    return sum(vals) / len(vals) if vals else None


def body_line_dev(joints: Joints, min_vis: float) -> float | None:
    """푸시업 몸통 이탈 = 180 − (어깨–엉덩이–발목 내각), 보이는 쪽 평균."""
    ang = _mean_of_sides(joints, (LEFT_BODY_LINE, RIGHT_BODY_LINE), min_vis)
    return None if ang is None else FULL_EXTENSION_DEG - ang


def knee_angle(joints: Joints, min_vis: float) -> float | None:
    """무릎 내각(엉덩이–무릎–발목), 보이는 쪽 평균."""
    return _mean_of_sides(joints, (LEFT_LEG3, RIGHT_LEG3), min_vis)


def hip_spread(joints: Joints, min_vis: float) -> float | None:
    """런지 보폭 = |왼쪽 − 오른쪽 엉덩이 내각(어깨–엉덩이–무릎)|. 양쪽이 다 보여야 계산한다."""
    left = _triple_angle(joints, LEFT_TORSO_THIGH, min_vis)
    right = _triple_angle(joints, RIGHT_TORSO_THIGH, min_vis)
    if left is None or right is None:
        return None
    return abs(left[0] - right[0])


#: 푸시업: 판정 = 팔꿈치 내각, 보조 = 몸통 이탈, 유지 = 무릎 내각 (D-78)
PUSHUP_SPEC = ChainSpec(LEFT_ARM, RIGHT_ARM, body_line_dev, hold=(LEFT_LEG3, RIGHT_LEG3))
SITUP_SPEC = ChainSpec(
    LEFT_TORSO_FLOOR, RIGHT_TORSO_FLOOR, knee_angle, aux=(LEFT_TORSO_THIGH, RIGHT_TORSO_THIGH)
)
#: 런지: 판정 = 무릎 내각, 보조 = 좌우 엉덩이 각도 차 (D-71)
LUNGE_SPEC = ChainSpec(LEFT_LEG3, RIGHT_LEG3, hip_spread)
#: 인버티드 숄더 프레스: 판정 = 팔꿈치 내각, 둘째 = 엉덩이 각도(어깨–엉덩이–발목),
#: 보조 = 무릎 내각 (D-72)
INVERTED_SHOULDER_PRESS_SPEC = ChainSpec(
    LEFT_ARM, RIGHT_ARM, knee_angle, aux=(LEFT_BODY_LINE, RIGHT_BODY_LINE)
)
#: 글루트 브릿지: 판정 = 180 − 엉덩이 내각(어깨–엉덩이–무릎), 보조 = 무릎 (D-73)
GLUTE_BRIDGE_SPEC = ChainSpec(LEFT_TORSO_THIGH, RIGHT_TORSO_THIGH, knee_angle, invert=True)
#: 사이드 레그 리프트: 판정 = 180 − 다리 벌림(왼·오른 엉덩이→발목 선 사이 각), 보조 = 무릎 (D-77)
SIDE_LEG_LIFT_SPEC = ChainSpec(LEFT_LEG3, RIGHT_LEG3, knee_angle, invert=True, pair=True)


_LEFT_ARM_LINE = (Joint.LEFT_SHOULDER, Joint.LEFT_WRIST)
_RIGHT_ARM_LINE = (Joint.RIGHT_SHOULDER, Joint.RIGHT_WRIST)
LEFT_ARM_REACH: Triple = (Joint.LEFT_HIP, Joint.LEFT_SHOULDER, Joint.LEFT_WRIST)
RIGHT_ARM_REACH: Triple = (Joint.RIGHT_HIP, Joint.RIGHT_SHOULDER, Joint.RIGHT_WRIST)


def arm_support(joints: Joints, min_vis: float) -> float | None:
    """팔 지지 각도 = 180 − (어깨→손목 선이 화면 아래 방향에서 기운 각도), 보이는 쪽 평균.

    손을 어깨 바로 아래 바닥에 짚으면 약 180°, 팔이 수평(옆에 둠·머리 위로 뻗음)이면 약 90°.
    화면 아래를 중력 방향으로 보므로 폰을 세로로 세워 둔다고 가정한다 (자세 확인 D-75와 같음).
    """
    vals: list[float] = []
    for sj, wj in (_LEFT_ARM_LINE, _RIGHT_ARM_LINE):
        sh, wr = _vis(joints[sj], min_vis), _vis(joints[wj], min_vis)
        if sh is None or wr is None:
            continue
        tilt = tilt_from_vertical_deg((sh.x, sh.y), (wr.x, wr.y))
        if tilt is not None:
            vals.append(FULL_EXTENSION_DEG - tilt)
    return sum(vals) / len(vals) if vals else None


def arm_reach(joints: Joints, min_vis: float) -> float | None:
    """팔 뻗음 = 엉덩이–어깨–손목 내각, 보이는 쪽 평균.

    팔을 머리 위로 뻗으면 약 180°, 옆에 두면 작다.
    """
    return _mean_of_sides(joints, (LEFT_ARM_REACH, RIGHT_ARM_REACH), min_vis)


def right_hip_angle(joints: Joints, min_vis: float) -> float | None:
    """오른쪽 엉덩이 내각(어깨–엉덩이–무릎). 왼다리 추출기의 '반대 다리' 값 (D-83)."""
    r = _triple_angle(joints, RIGHT_TORSO_THIGH, min_vis)
    return None if r is None else r[0]


def left_hip_angle(joints: Joints, min_vis: float) -> float | None:
    """왼쪽 엉덩이 내각(어깨–엉덩이–무릎). 오른다리 추출기의 '반대 다리' 값 (D-83)."""
    r = _triple_angle(joints, LEFT_TORSO_THIGH, min_vis)
    return None if r is None else r[0]


#: 하이 니 다리별 사슬: 판정 = 그 다리 엉덩이 내각, 보조 = 반대 다리 엉덩이 내각 (D-83)
HIGH_KNEE_LEFT_SPEC = ChainSpec(LEFT_TORSO_THIGH, LEFT_TORSO_THIGH, right_hip_angle, single=True)
HIGH_KNEE_RIGHT_SPEC = ChainSpec(RIGHT_TORSO_THIGH, RIGHT_TORSO_THIGH, left_hip_angle, single=True)
#: 마운틴 클라이머 다리별 사슬: 하이 니와 같고, 유지 = 팔 지지 각도 (D-84)
MOUNTAIN_CLIMBER_LEFT_SPEC = ChainSpec(
    LEFT_TORSO_THIGH, LEFT_TORSO_THIGH, right_hip_angle, single=True, hold_fn=arm_support
)
MOUNTAIN_CLIMBER_RIGHT_SPEC = ChainSpec(
    RIGHT_TORSO_THIGH, RIGHT_TORSO_THIGH, left_hip_angle, single=True, hold_fn=arm_support
)
#: 하이 니·마운틴 클라이머 확신도용: 두 다리가 모두 보여야 유효 프레임 (쌍으로 세므로)
BOTH_LEGS_QUALITY_SPEC = ChainSpec(LEFT_TORSO_THIGH, RIGHT_TORSO_THIGH, knee_angle, pair=True)
#: 슈퍼맨: 판정 = 몸 활 각도(어깨–엉덩이–발목), 보조 = 팔 뻗음 (D-85)
SUPERMAN_SPEC = ChainSpec(LEFT_BODY_LINE, RIGHT_BODY_LINE, arm_reach)
#: 돈키 킥: 판정 = 180 − 엉덩이 내각, 좌우 중 작은 쪽(찬 다리), 보조 = 무릎, 유지 = 팔 지지 (D-86)
DONKEY_KICK_SPEC = ChainSpec(
    LEFT_TORSO_THIGH,
    RIGHT_TORSO_THIGH,
    knee_angle,
    invert=True,
    pick="min",
    hold_fn=arm_support,
)


def _torso_leg_ratio(joints: Joints, min_vis: float) -> float | None:
    """보이는 쪽마다 어깨–엉덩이 ÷ (엉덩이–무릎 + 무릎–발목)의 평균. 자세와 무관하게 거의 일정."""
    vals: list[float] = []
    for side in (_LEFT_BODY, _RIGHT_BODY):
        pts = [_vis(joints[j], min_vis) for j in side]
        if any(p is None for p in pts):
            continue
        sh, hip, knee, ankle = ((p.x, p.y) for p in pts if p is not None)
        limb = distance(hip, knee) + distance(knee, ankle)
        if limb > 0:
            vals.append(distance(sh, hip) / limb)
    return sum(vals) / len(vals) if vals else None


_ANKLES = (Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE)
_HIP_ANKLE = ((Joint.LEFT_HIP, Joint.LEFT_ANKLE), (Joint.RIGHT_HIP, Joint.RIGHT_ANKLE))


def floor_and_leg(joints: Joints, min_vis: float) -> tuple[float | None, float | None]:
    """(바닥 쪽 발목 y, 엉덩이–발목 거리 평균). 안 보이면 각각 None."""
    ankles = [p.y for j in _ANKLES if (p := _vis(joints[j], min_vis)) is not None]
    legs = [
        distance((h.x, h.y), (a.x, a.y))
        for hj, aj in _HIP_ANKLE
        if (h := _vis(joints[hj], min_vis)) is not None
        and (a := _vis(joints[aj], min_vis)) is not None
    ]
    return (max(ankles) if ankles else None), (sum(legs) / len(legs) if legs else None)


def chain_quality(spec: ChainSpec) -> Callable[[SkeletonFrame, float], tuple[bool, float | None]]:
    """확신도용 프레임 품질 함수: (유효 프레임 여부, 쓰인 판정 관절 평균 가시도)."""

    def quality(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
        if frame.joints is None:
            return False, None
        sides = _sides(frame.joints, spec, min_visibility)
        if not sides:
            return False, None
        return True, sum(v for _, v in sides) / len(sides)

    return quality


class ChainFeatureExtractor:
    """스트리밍 특징 추출기. 프레임을 시각 순서대로 `update`에 넣는다."""

    def __init__(
        self, cfg: FeaturesCfg, spec: ChainSpec, posture: TorsoRangeCfg | None = None
    ) -> None:
        self._cfg = cfg
        self._spec = spec
        #: 자세 확인 범위 (D-75). 벗어난 프레임은 무효. None이면 확인하지 않음
        self._posture = posture
        self._filter = OneEuroFilter(
            cfg.one_euro.min_cutoff, cfg.one_euro.beta, cfg.one_euro.d_cutoff
        )
        self._aux_filter = OneEuroFilter(
            cfg.one_euro.min_cutoff, cfg.one_euro.beta, cfg.one_euro.d_cutoff
        )
        self._last_valid_t: int | None = None

    def update(self, frame: SkeletonFrame) -> ChainFeatures:
        """프레임 1개를 처리한다."""
        joints = frame.joints
        mv = self._cfg.min_visibility
        if joints is None or not posture_ok(joints, mv, self._posture):
            return ChainFeatures(frame.t, False)
        sides = _sides(joints, self._spec, mv)
        if not sides:
            return ChainFeatures(frame.t, False)

        if (
            self._last_valid_t is not None
            and frame.t - self._last_valid_t >= self._cfg.filter_reset_gap_ms
        ):
            self._filter.reset()
            self._aux_filter.reset()
        self._last_valid_t = frame.t

        if self._spec.invert:
            sides = [(FULL_EXTENSION_DEG - a, v) for a, v in sides]
        raw = (
            min(a for a, _ in sides)
            if self._spec.pick == "min"
            else sum(a for a, _ in sides) / len(sides)
        )
        aux: float | None = None
        if self._spec.aux is not None or self._spec.aux_fn is not None:
            aux_raw = (
                _mean_of_sides(joints, self._spec.aux, mv)
                if self._spec.aux is not None
                else self._spec.aux_fn(joints, mv)  # type: ignore[misc]
            )
            aux = None if aux_raw is None else self._aux_filter(aux_raw, frame.t)
        if self._spec.hold is not None:
            hold = _mean_of_sides(joints, self._spec.hold, mv)
        elif self._spec.hold_fn is not None:
            hold = self._spec.hold_fn(joints, mv)
        else:
            hold = None
        floor_y, leg_length = floor_and_leg(joints, mv)
        return ChainFeatures(
            t=frame.t,
            valid=True,
            hold_angle=hold,
            floor_y=floor_y,
            leg_length=leg_length,
            angle=self._filter(raw, frame.t),
            angle_raw=raw,
            aux_angle=aux,
            asymmetry=abs(sides[0][0] - sides[1][0]) if len(sides) == 2 else None,
            form_angle=self._spec.form(joints, mv),
            core_visibility=sum(v for _, v in sides) / len(sides),
            torso_leg_ratio=_torso_leg_ratio(joints, mv),
        )


# --- 리버스 크런치·사이드 런지·버드독 (D-89~D-91) -----------------------------


def torso_tilt(joints: Joints, min_vis: float) -> float | None:
    """상체 방향(엉덩이→어깨 선이 화면 위쪽에서 기운 각도). 누우면 약 90°, 서면 0° (D-75와 같음)."""
    return torso_from_up(joints, min_vis)


def _one_arm_support(joints: Joints, sj: Joint, wj: Joint, min_vis: float) -> float | None:
    sh, wr = _vis(joints[sj], min_vis), _vis(joints[wj], min_vis)
    if sh is None or wr is None:
        return None
    tilt = tilt_from_vertical_deg((sh.x, sh.y), (wr.x, wr.y))
    return None if tilt is None else FULL_EXTENSION_DEG - tilt


def left_arm_support(joints: Joints, min_vis: float) -> float | None:
    """왼팔 하나의 팔 지지 각도 (`arm_support`와 같은 정의)."""
    return _one_arm_support(joints, *_LEFT_ARM_LINE, min_vis)


def right_arm_support(joints: Joints, min_vis: float) -> float | None:
    """오른팔 하나의 팔 지지 각도."""
    return _one_arm_support(joints, *_RIGHT_ARM_LINE, min_vis)


def left_knee_angle(joints: Joints, min_vis: float) -> float | None:
    r = _triple_angle(joints, LEFT_LEG3, min_vis)
    return None if r is None else r[0]


def right_knee_angle(joints: Joints, min_vis: float) -> float | None:
    r = _triple_angle(joints, RIGHT_LEG3, min_vis)
    return None if r is None else r[0]


def leg_spread_complement(joints: Joints, min_vis: float) -> float | None:
    """180 − 다리 벌림(왼·오른 엉덩이→발목 선 사이 각도). 두 다리가 다 보여야 계산한다.

    둘째 판정 각도는 '작을수록 잘 됨'이라 벌림을 180에서 뺀다 (사이드 런지, D-90).
    """
    r = _pair_angle(joints, _SPREAD_SPEC, min_vis)
    return None if r is None else FULL_EXTENSION_DEG - r[0]


def _bird_dog_judge(arm: Triple, leg: Triple) -> JudgeFn:
    def judge(joints: Joints, min_vis: float) -> tuple[float, float] | None:
        a = _triple_angle(joints, arm, min_vis)
        g = _triple_angle(joints, leg, min_vis)
        if a is None or g is None:
            return None
        return FULL_EXTENSION_DEG - min(a[0], g[0]), (a[1] + g[1]) / 2.0

    return judge


_SPREAD_SPEC = ChainSpec(LEFT_LEG3, RIGHT_LEG3, knee_angle, pair=True)

#: 리버스 크런치: 판정 = 엉덩이 내각, 보조 = 무릎, 유지 = 상체 방향(누워 있음) (D-89)
REVERSE_CRUNCH_SPEC = ChainSpec(LEFT_TORSO_THIGH, RIGHT_TORSO_THIGH, knee_angle, hold_fn=torso_tilt)
#: 사이드 런지 다리별: 판정 = 그 다리 무릎, 보조 = 반대 다리 무릎, 둘째 = 180 − 다리 벌림 (D-90)
SIDE_LUNGE_LEFT_SPEC = ChainSpec(
    LEFT_LEG3, LEFT_LEG3, right_knee_angle, single=True, aux_fn=leg_spread_complement
)
SIDE_LUNGE_RIGHT_SPEC = ChainSpec(
    RIGHT_LEG3, RIGHT_LEG3, left_knee_angle, single=True, aux_fn=leg_spread_complement
)
#: 버드독 쪽별: '왼쪽 동작' = 왼팔 + 오른다리, 보조 = 받치는 오른팔의 팔 지지 (D-91)
BIRD_DOG_LEFT_SPEC = ChainSpec(
    LEFT_ARM_REACH,
    LEFT_ARM_REACH,
    right_arm_support,
    single=True,
    judge_fn=_bird_dog_judge(LEFT_ARM_REACH, RIGHT_TORSO_THIGH),
)
BIRD_DOG_RIGHT_SPEC = ChainSpec(
    RIGHT_ARM_REACH,
    RIGHT_ARM_REACH,
    left_arm_support,
    single=True,
    judge_fn=_bird_dog_judge(RIGHT_ARM_REACH, LEFT_TORSO_THIGH),
)


@dataclass(frozen=True, slots=True)
class AlternatingFeatures:
    """다리를 번갈아 하는 종목의 프레임 특징: 다리별 특징 두 개 (D-83).

    이상 징후·데모가 쓰는 공통 속성(`t`, `valid`, `torso_leg_ratio`, `angle`)도 준다.
    """

    t: int
    left: ChainFeatures
    right: ChainFeatures

    @property
    def valid(self) -> bool:
        """두 다리가 모두 보여야 유효 (쌍으로 세므로)."""
        return self.left.valid and self.right.valid

    @property
    def angle(self) -> float | None:
        """더 많이 굽힌 다리의 판정 각도 (화면 표시용)."""
        vals = [f.angle for f in (self.left, self.right) if f.angle is not None]
        return min(vals) if vals else None

    @property
    def torso_leg_ratio(self) -> float | None:
        return self.left.torso_leg_ratio


class AlternatingFeatureExtractor:
    """다리마다 `ChainFeatureExtractor`를 하나씩 둔 스트리밍 추출기 (D-83)."""

    def __init__(
        self,
        cfg: FeaturesCfg,
        left: ChainSpec,
        right: ChainSpec,
        posture: TorsoRangeCfg | None = None,
    ) -> None:
        self._left = ChainFeatureExtractor(cfg, left, posture)
        self._right = ChainFeatureExtractor(cfg, right, posture)

    def update(self, frame: SkeletonFrame) -> AlternatingFeatures:
        return AlternatingFeatures(frame.t, self._left.update(frame), self._right.update(frame))
