"""굽혔다 펴는 종목(푸시업·윗몸 일으키기)의 프레임 특징.

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

자세 각도(`posture_angle`, 필터 전 값)는 렙을 셀 자세인지 확인하는 종목만 쓴다.
- 푸시업: 어깨 중점에서 발목 중점(안 보이면 엉덩이 중점)으로 가는 선이 **화면 수평선**에서
  기울어진 각도(0° = 엎드려 수평). 어깨–발목 선은 엉덩이가 처지거나 들려도 변하지 않는다.
  발목은 잘 안 잡힐 때가 많아 엉덩이로 대신한다. 폰이 바닥과 수평으로 놓였다고 가정한다 (D-71).

보조 각도(`form_angle`, 필터 전 값)는 종목마다 다르다.
- 푸시업 `body_line_dev`: 180 − (어깨–엉덩이–발목 내각). 몸이 일직선이면 0°.
- 윗몸 일으키기 `knee_angle`: 엉덩이–무릎–발목 내각.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rep_engine.adapters import Point, SkeletonFrame
from rep_engine.config import FeaturesCfg
from rep_engine.features.filters import OneEuroFilter
from rep_engine.features.geometry import angle_deg, distance, midpoint, tilt_from_vertical_deg
from rep_engine.landmarks import Joint

Triple = tuple[Joint, Joint, Joint]
Joints = tuple[Point | None, ...]
#: (관절 목록, min_visibility) → 보조 각도(도) 또는 None
FormFn = Callable[[Joints, float], float | None]

FULL_EXTENSION_DEG = 180.0  # 일직선 = 180° (정의상 상수)
HORIZONTAL_FROM_VERTICAL_DEG = 90.0  # 수평선은 수직선에서 90° (정의상 상수)

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
    #: 렙을 셀 자세인지 판단하는 각도 (모듈 설명 참고). 종목에 없거나 관절이 안 보이면 None
    posture_angle: float | None = None
    #: 종목별 보조 각도 (모듈 설명 참고)
    form_angle: float | None = None
    core_visibility: float | None = None
    #: 상체 길이 ÷ (허벅지+정강이). 사람 교체 탐지(BODY_PROPORTION_SHIFT)용
    torso_leg_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class ChainSpec:
    """종목의 판정 사슬(좌·우), 보조 각도, 둘째 판정 사슬, 자세 각도 (없으면 None)."""

    left: Triple
    right: Triple
    form: FormFn
    aux: tuple[Triple, Triple] | None = None
    posture: FormFn | None = None


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


def torso_tilt_from_horizontal(joints: Joints, min_vis: float) -> float | None:
    """어깨 중점 → 발목 중점(안 보이면 엉덩이 중점) 선이 화면 수평선에서 기울어진 각도(0~90°).

    어깨가 안 보이거나, 발목과 엉덩이가 모두 안 보이면 None.
    """
    sh = [p for j in (Joint.LEFT_SHOULDER, Joint.RIGHT_SHOULDER) if (p := _vis(joints[j], min_vis))]
    far = [p for j in (Joint.LEFT_ANKLE, Joint.RIGHT_ANKLE) if (p := _vis(joints[j], min_vis))] or [
        p for j in (Joint.LEFT_HIP, Joint.RIGHT_HIP) if (p := _vis(joints[j], min_vis))
    ]
    if not sh or not far:
        return None
    top = midpoint((sh[0].x, sh[0].y), (sh[-1].x, sh[-1].y))
    bottom = midpoint((far[0].x, far[0].y), (far[-1].x, far[-1].y))
    tilt = tilt_from_vertical_deg(top, bottom)
    return None if tilt is None else abs(HORIZONTAL_FROM_VERTICAL_DEG - tilt)


PUSHUP_SPEC = ChainSpec(LEFT_ARM, RIGHT_ARM, body_line_dev, posture=torso_tilt_from_horizontal)
SITUP_SPEC = ChainSpec(
    LEFT_TORSO_FLOOR, RIGHT_TORSO_FLOOR, knee_angle, aux=(LEFT_TORSO_THIGH, RIGHT_TORSO_THIGH)
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


def chain_quality(spec: ChainSpec) -> Callable[[SkeletonFrame, float], tuple[bool, float | None]]:
    """확신도용 프레임 품질 함수: (유효 프레임 여부, 쓰인 판정 관절 평균 가시도)."""

    def quality(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
        if frame.joints is None:
            return False, None
        sides = [
            r
            for tri in (spec.left, spec.right)
            if (r := _triple_angle(frame.joints, tri, min_visibility)) is not None
        ]
        if not sides:
            return False, None
        return True, sum(v for _, v in sides) / len(sides)

    return quality


class ChainFeatureExtractor:
    """스트리밍 특징 추출기. 프레임을 시각 순서대로 `update`에 넣는다."""

    def __init__(self, cfg: FeaturesCfg, spec: ChainSpec) -> None:
        self._cfg = cfg
        self._spec = spec
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
        if joints is None:
            return ChainFeatures(frame.t, False)
        mv = self._cfg.min_visibility
        sides = [
            r
            for tri in (self._spec.left, self._spec.right)
            if (r := _triple_angle(joints, tri, mv)) is not None
        ]
        if not sides:
            return ChainFeatures(frame.t, False)

        if (
            self._last_valid_t is not None
            and frame.t - self._last_valid_t >= self._cfg.filter_reset_gap_ms
        ):
            self._filter.reset()
            self._aux_filter.reset()
        self._last_valid_t = frame.t

        raw = sum(a for a, _ in sides) / len(sides)
        aux: float | None = None
        if self._spec.aux is not None:
            aux_raw = _mean_of_sides(joints, self._spec.aux, mv)
            aux = None if aux_raw is None else self._aux_filter(aux_raw, frame.t)
        return ChainFeatures(
            t=frame.t,
            valid=True,
            angle=self._filter(raw, frame.t),
            angle_raw=raw,
            aux_angle=aux,
            posture_angle=None if self._spec.posture is None else self._spec.posture(joints, mv),
            asymmetry=abs(sides[0][0] - sides[1][0]) if len(sides) == 2 else None,
            form_angle=self._spec.form(joints, mv),
            core_visibility=sum(v for _, v in sides) / len(sides),
            torso_leg_ratio=_torso_leg_ratio(joints, mv),
        )
