"""카탈로그 설정(`config/catalog/<catalogVersion>.yaml`) 로드·검증.

모든 판정 기준값은 이 설정에서 읽는다. 모델 의존 기준값(min_visibility 등)은
`model_overrides.<family>`로 모델 계열별 덮어쓰기를 할 수 있다.
"""

from __future__ import annotations

import copy
import math
import re
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from rep_engine.errors import CatalogNotFoundError, ConfigError

DEFAULT_CATALOG_DIR = Path(__file__).resolve().parent.parent / "config" / "catalog"
_VERSION_RE = re.compile(r"^cat_[0-9A-Za-z_\-]+$")
#: 가중치 합 비교 허용 오차 (부동소수 표현 오차용)
_WEIGHT_SUM_TOL = 1e-6


class _Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OneEuroCfg(_Cfg):
    min_cutoff: float = Field(gt=0)
    beta: float = Field(ge=0)
    d_cutoff: float = Field(gt=0)


class FeaturesCfg(_Cfg):
    min_visibility: float = Field(ge=0, le=1)
    one_euro: OneEuroCfg
    filter_reset_gap_ms: int = Field(gt=0)
    calibration_window_ms: int = Field(gt=0)


class SquatCfg(_Cfg):
    """스쿼트 판정 기준. 각도는 kneeAngle(내각, 도), 시간은 ms."""

    descent_start_angle: float = Field(gt=0, lt=180)
    attempt_angle: float = Field(gt=0, lt=180)
    depth_accept_angle: float = Field(gt=0, lt=180)
    stand_angle: float = Field(gt=0, le=180)
    bottom_hysteresis_deg: float = Field(gt=0)
    depth_mode: Literal["angle", "angle_or_hip_drop"]
    hip_drop_accept: float = Field(gt=0)
    min_rep_ms: int = Field(gt=0)
    min_descent_ms: int = Field(gt=0)
    max_rep_ms: int = Field(gt=0)
    max_invalid_ratio_in_rep: float = Field(ge=0, le=1)
    max_gap_in_rep_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def _order(self) -> SquatCfg:
        if not (self.depth_accept_angle < self.attempt_angle < self.descent_start_angle):
            raise ValueError("depth_accept_angle < attempt_angle < descent_start_angle 이어야 함")
        if self.stand_angle < self.descent_start_angle:
            raise ValueError("stand_angle >= descent_start_angle 이어야 함")
        if not (self.min_descent_ms < self.min_rep_ms < self.max_rep_ms):
            raise ValueError("min_descent_ms < min_rep_ms < max_rep_ms 이어야 함")
        return self


class FlexionCfg(_Cfg):
    """굽혔다 펴는 렙 판정 기준 (푸시업·윗몸 일으키기 공통). 각도는 판정 각도(내각, 도), 시간은 ms.

    판정 각도는 쉬는 자세에서 크고(`rest_angle` 이상) 굽힐수록 작아진다.
    `flex_start_angle` 아래로 내려가면 렙 시작, `attempt_angle` 아래까지 가야 시도로 기록,
    `depth_accept_angle` 이하까지 가야 인정, 다시 `rest_angle` 이상이면 렙 끝.
    """

    flex_start_angle: float = Field(gt=0, lt=180)
    attempt_angle: float = Field(gt=0, lt=180)
    depth_accept_angle: float = Field(gt=0, lt=180)
    rest_angle: float = Field(gt=0, le=180)
    bottom_hysteresis_deg: float = Field(gt=0)
    min_rep_ms: int = Field(gt=0)
    min_descent_ms: int = Field(gt=0)
    max_rep_ms: int = Field(gt=0)
    max_invalid_ratio_in_rep: float = Field(ge=0, le=1)
    max_gap_in_rep_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def _order(self) -> Self:
        if not (self.depth_accept_angle < self.attempt_angle < self.flex_start_angle):
            raise ValueError("depth_accept_angle < attempt_angle < flex_start_angle 이어야 함")
        if self.rest_angle < self.flex_start_angle:
            raise ValueError("rest_angle >= flex_start_angle 이어야 함")
        if not (self.min_descent_ms < self.min_rep_ms < self.max_rep_ms):
            raise ValueError("min_descent_ms < min_rep_ms < max_rep_ms 이어야 함")
        return self


class FeetDownCfg(_Cfg):
    """발이 바닥에 붙어 있어야 하는 종목의 '발 뜸' 판정 (D-79, D-82).

    바닥 높이 = 최근 `floor_window_ms` 동안 바닥 쪽 발목(화면 y가 가장 큰 발목)의 가장 낮은 위치.
    바닥 쪽 발목이 그보다 다리 길이 × `max_foot_lift_ratio` 넘게 올라가면 '떴다'.
    렙 시작 `airborne_lookback_ms` 전부터 렙 끝까지 한 번이라도 떴으면 인정하지 않는다.
    """

    max_foot_lift_ratio: float = Field(gt=0)
    floor_window_ms: int = Field(gt=0)
    airborne_lookback_ms: int = Field(ge=0)


class PushupCfg(FlexionCfg):
    """푸시업. 판정 각도 = 팔꿈치 내각(어깨–팔꿈치–손목)."""

    #: 인정 렙 평균 몸통 이탈(180 − 어깨–엉덩이–발목 내각)이 이 값을 넘으면 BODY_LINE_BROKEN
    body_line_dev_deg: float = Field(ge=0)
    #: 렙 내내 무릎 내각(엉덩이–무릎–발목)이 이 값 이상이어야 인정 (무릎 대고 하기 제외, D-78).
    #: 없으면 확인하지 않음 (cat_2026-11-17 전 카탈로그)
    min_knee_angle: float | None = Field(default=None, gt=0, le=180)


class SitupCfg(FlexionCfg):
    """윗몸 일으키기. 판정 각도 = 상체 각도(어깨–엉덩이–발목 내각, 180 − 상체가 들린 각도).

    상체 각도 기준(`depth_accept_angle`)과 엉덩이 각도 기준(`hip_accept_angle`)을 **둘 다** 넘어야
    인정한다 (D-70).
    """

    #: 렙 동안 엉덩이 내각(어깨–엉덩이–무릎) 최저값이 이 값 이하여야 인정
    hip_accept_angle: float = Field(gt=0, lt=180)
    #: 발이 바닥에 붙어 있어야 인정 (다리를 들어 배에 붙이기 제외, D-82). 없으면 확인하지 않음
    feet_down: FeetDownCfg | None = None


class LungeCfg(FlexionCfg):
    """런지. 판정 각도 = 무릎 내각(엉덩이–무릎–발목, 보이는 다리 평균) (D-71).

    스쿼트와 구별하려고 최저점의 좌우 엉덩이 각도 차가 `min_hip_spread_deg` 이상이어야
    인정한다.
    """

    #: 최저점에서 |왼쪽 − 오른쪽 엉덩이 내각(어깨–엉덩이–무릎)|이 이 값 이상이어야 인정
    min_hip_spread_deg: float = Field(gt=0, lt=180)
    #: 점프 판정 (D-79). 점프 착지 뒤 렙도 잡도록 렙 시작 전부터 본다
    feet_down: FeetDownCfg


class InvertedShoulderPressCfg(FlexionCfg):
    """인버티드 숄더 프레스(파이크 자세). 판정 각도 = 팔꿈치 내각(어깨–팔꿈치–손목) (D-72).

    파이크 자세 확인: 렙 동안 엉덩이 각도(어깨–엉덩이–발목) 최저값이 `pike_hip_accept_angle` 이하.
    """

    pike_hip_accept_angle: float = Field(gt=0, lt=180)


class GluteBridgeCfg(FlexionCfg):
    """글루트 브릿지. 판정 각도 = 엉덩이 굽힘 = 180 − 엉덩이 내각(어깨–엉덩이–무릎) (D-73).

    누우면 약 45°, 엉덩이를 들어 몸이 일직선에 가까워질수록 0°에 가까워진다. 그래서 다른
    종목처럼 '쉬는 자세에서 크고 동작할수록 작아지는' 각도가 되어 같은 상태 머신을 쓴다.
    """


class SideLegLiftCfg(FlexionCfg):
    """사이드 레그 리프트. 판정 각도 = 180 − 다리 벌림 (D-77).

    다리 벌림 = 왼쪽·오른쪽 엉덩이→발목 선 사이 각도. 다리를 모으면 약 0°(판정 각도 약 180°),
    위쪽 다리를 들수록 커진다(판정 각도는 작아짐). 옆으로 누운 몸의 앞쪽을 카메라가 보게 찍는다.
    """


class AlternatingCfg(FlexionCfg):
    """다리를 번갈아 하는 종목(하이 니·마운틴 클라이머)의 **다리 하나** 판정 기준 (D-83).

    판정 각도 = 그 다리의 엉덩이 내각(어깨–엉덩이–무릎). 다리마다 따로 굽혔다 펴기를 판정하고,
    왼다리 1번 + 오른다리 1번을 묶어 1렙으로 센다. 두 다리가 모두 인정이어야 그 렙이 인정이다.
    시간 기준(`min_rep_ms` 등)은 다리 하나 기준이다.
    """

    #: 이 다리가 가장 높이 올라간 순간, 반대쪽 다리의 엉덩이 내각이 이 값 이상이어야 인정
    #: (두 다리를 함께 굽히는 스쿼트·웅크리기 제외). 반대쪽 다리가 안 보이면 OUT_OF_FRAME
    min_other_hip_angle: float = Field(gt=0, le=180)
    #: 한 쌍으로 묶을 수 있는 두 다리 사이 최대 간격 (앞 다리 끝 → 뒷 다리 시작, ms).
    #: 넘으면 앞 다리는 짝 없이 버린다
    max_pair_gap_ms: int = Field(gt=0)


class HighKneeCfg(AlternatingCfg):
    """하이 니 (D-83). 선 자세에서 무릎을 번갈아 엉덩이 높이 가까이 올린다."""


class MountainClimberCfg(AlternatingCfg):
    """마운틴 클라이머 (D-84). 플랭크 자세에서 무릎을 번갈아 가슴 쪽으로 당긴다."""

    #: 렙 내내 팔 지지 각도(180 − 어깨→손목 선이 아래 방향에서 기운 각도)가 이 값 이상이어야 인정.
    #: 손을 바닥에 짚고 팔이 몸을 받치는지 본다 (누워서 무릎 당기기 제외)
    min_arm_support_angle: float = Field(gt=0, le=180)


class SupermanCfg(FlexionCfg):
    """슈퍼맨 (D-85). 판정 각도 = 몸 활 각도(어깨–엉덩이–발목 내각).

    엎드려 일직선이면 약 180°, 팔·가슴과 다리를 들수록 작아진다. 들었다 내리면 1렙.
    """

    #: 가장 높이 든 순간 팔 뻗음(엉덩이–어깨–손목 내각)이 이 값 이상이어야 인정
    #: (팔을 머리 위로 뻗음. 팔을 옆에 둔 글루트 브릿지와 구별)
    min_arm_reach_angle: float = Field(gt=0, le=180)


class DonkeyKickCfg(FlexionCfg):
    """돈키 킥 (D-86). 판정 각도 = 180 − 엉덩이 내각(어깨–엉덩이–무릎), 좌우 중 작은 쪽(찬 다리).

    네발 자세에서 허벅지가 아래로 내려 있으면 약 90°, 다리를 뒤로 차 올려 허벅지가 몸통과
    일직선에 가까워질수록 0°에 가까워진다.
    """

    #: 렙 내내 팔 지지 각도가 이 값 이상이어야 인정
    #: (손을 바닥에 짚은 네발 자세, 마운틴 클라이머와 같음)
    min_arm_support_angle: float = Field(gt=0, le=180)


class TorsoRangeCfg(_Cfg):
    """상체 방향 허용 범위 (D-75). 상체 방향 = 엉덩이→어깨 선이 화면 위쪽에서 기운 각도.

    0° = 똑바로 섬, 90° = 수평(누움·엎드림), 180° = 거꾸로. 폰을 세로로 세워 둔다고 가정한다.
    """

    min_deg: float = Field(ge=0, le=180)
    max_deg: float = Field(ge=0, le=180)

    @model_validator(mode="after")
    def _order(self) -> TorsoRangeCfg:
        if not self.min_deg < self.max_deg:
            raise ValueError("min_deg < max_deg 이어야 함")
        return self


class PostureCfg(_Cfg):
    """종목별 자세(서기·엎드리기·눕기) 확인 (D-75). 범위를 벗어난 프레임은 무효 프레임이 된다.

    종목 키가 없으면 그 종목은 자세를 확인하지 않는다. 옛 카탈로그에는 이 섹션이 없다.
    """

    squat: TorsoRangeCfg | None = None
    pushup: TorsoRangeCfg | None = None
    situp: TorsoRangeCfg | None = None
    lunge: TorsoRangeCfg | None = None
    inverted_shoulder_press: TorsoRangeCfg | None = None
    glute_bridge: TorsoRangeCfg | None = None
    side_leg_lift: TorsoRangeCfg | None = None
    high_knee: TorsoRangeCfg | None = None
    mountain_climber: TorsoRangeCfg | None = None
    superman: TorsoRangeCfg | None = None
    donkey_kick: TorsoRangeCfg | None = None


class LivenessCfg(_Cfg):
    """무작위 동작 확인 기준.

    머리 높이 = 어깨 중점 y − head_height_ratio × 어깨 너비 (코를 서버로 받지 않으므로, D-02).
    손 든 판정 = 손목 y < 머리 높이 − hand_above_head_margin × 어깨 너비.
    """

    hand_above_head_margin: float = Field(ge=0)
    head_height_ratio: float = Field(ge=0)
    liveness_hold_ms: int = Field(gt=0)
    wrong_hand_hold_ms: int = Field(gt=0)
    min_valid_ratio: float = Field(ge=0, le=1)


class WeightsCfg(_Cfg):
    vis: float = Field(ge=0)
    valid: float = Field(ge=0)
    track: float = Field(ge=0)
    consistency: float = Field(ge=0)
    unaccepted: float = Field(ge=0)

    @model_validator(mode="after")
    def _sum_one(self) -> WeightsCfg:
        total = self.vis + self.valid + self.track + self.consistency + self.unaccepted
        if not math.isclose(total, 1.0, abs_tol=_WEIGHT_SUM_TOL):
            raise ValueError(f"confidence.weights 합이 1이 아님: {total}")
        return self


class ConsistencyKCfg(_Cfg):
    duration_cv: float = Field(gt=0)
    depth_std: float = Field(gt=0)


class ConfidenceCfg(_Cfg):
    weights: WeightsCfg
    consistency_k: ConsistencyKCfg
    min_reps_for_consistency: int = Field(ge=2)
    neutral_score: float = Field(ge=0, le=1)
    liveness_penalty: float = Field(ge=0, le=1)
    calibration: list[tuple[float, float]] = Field(min_length=2)

    @model_validator(mode="after")
    def _calibration(self) -> ConfidenceCfg:
        pts = self.calibration
        for raw, cal in pts:
            if not (0.0 <= raw <= 1.0 and 0.0 <= cal <= 1.0):
                raise ValueError("calibration 점은 0~1 범위여야 함")
        for (r0, c0), (r1, c1) in zip(pts, pts[1:], strict=False):
            if r1 <= r0:
                raise ValueError("calibration raw 값은 엄격히 오름차순이어야 함")
            if c1 < c0:
                raise ValueError("calibration 보정값은 감소하면 안 됨")
        if pts[0][0] != 0.0 or pts[-1][0] != 1.0:
            raise ValueError("calibration은 raw 0과 1을 포함해야 함")
        return self


class FormTagsCfg(_Cfg):
    shallow_ratio: float = Field(ge=0, le=1)
    depth_std_deg: float = Field(ge=0)
    trunk_lean_deg: float = Field(ge=0)
    asymmetry_deg: float = Field(ge=0)
    too_fast_ratio: float = Field(ge=0, le=1)
    out_of_frame_ratio: float = Field(ge=0, le=1)


class AnomalyCfg(_Cfg):
    regular_timing_min_reps: int = Field(ge=2)
    regular_timing_std_ms: float = Field(ge=0)
    frozen_ms: int = Field(gt=0)
    frozen_motion_ratio: float = Field(ge=0)
    zero_jitter_min_ms: int = Field(gt=0)
    zero_jitter_ratio: float = Field(ge=0)
    stationary_speed_ratio: float = Field(gt=0)
    proportion_shift_ratio: float = Field(gt=0)
    reset_gap_ms: int = Field(gt=0)
    reset_count: int = Field(ge=1)
    min_avg_rep_ms: float = Field(gt=0)


class AnomalyOverrideCfg(_Cfg):
    """종목별 이상 징후 기준 덮어쓰기 (D-87). 적은 값만 `anomaly`를 덮어쓴다.

    값의 범위는 `AnomalyCfg`와 같고, 카탈로그를 읽을 때 합친 결과로 검증한다.
    """

    regular_timing_min_reps: int | None = None
    regular_timing_std_ms: float | None = None
    frozen_ms: int | None = None
    frozen_motion_ratio: float | None = None
    zero_jitter_min_ms: int | None = None
    zero_jitter_ratio: float | None = None
    stationary_speed_ratio: float | None = None
    proportion_shift_ratio: float | None = None
    reset_gap_ms: int | None = None
    reset_count: int | None = None
    min_avg_rep_ms: float | None = None


class AnomalyByExerciseCfg(_Cfg):
    """종목 섹션 이름 → 이상 징후 덮어쓰기 (D-87). 없는 종목은 공통 `anomaly`를 그대로 쓴다.

    빠른 종목(하이 니·마운틴 클라이머)은 공통 기준(렙 평균 1초 미만 = UNREALISTIC_PACE)으로는
    정상 동작도 이상으로 잡혀서 둔다.
    """

    squat: AnomalyOverrideCfg | None = None
    pushup: AnomalyOverrideCfg | None = None
    situp: AnomalyOverrideCfg | None = None
    lunge: AnomalyOverrideCfg | None = None
    inverted_shoulder_press: AnomalyOverrideCfg | None = None
    glute_bridge: AnomalyOverrideCfg | None = None
    side_leg_lift: AnomalyOverrideCfg | None = None
    high_knee: AnomalyOverrideCfg | None = None
    mountain_climber: AnomalyOverrideCfg | None = None
    superman: AnomalyOverrideCfg | None = None
    donkey_kick: AnomalyOverrideCfg | None = None


def merge_anomaly(base: AnomalyCfg, override: AnomalyOverrideCfg) -> AnomalyCfg:
    """공통 이상 징후 기준에 종목별 덮어쓰기를 합친다 (값 범위도 다시 검증)."""
    return AnomalyCfg.model_validate(
        {**base.model_dump(), **override.model_dump(exclude_none=True)}
    )


class RecountCfg(_Cfg):
    recount_tolerance: float = Field(ge=0)
    confidence_diff_warn: float = Field(ge=0, le=1)
    auto_approve_threshold: float = Field(ge=0, le=1)
    liveness_policy: Literal["restart", "review"]
    rep_match_iou: float = Field(gt=0, le=1)


class EngineConfig(_Cfg):
    """모델 덮어쓰기까지 적용된, 엔진이 실제로 쓰는 설정."""

    catalog_version: str
    #: 옛 카탈로그(cat_2026-11-01) 호환용. 종목별 기준은 아래 squat/pushup/situp 섹션이 정한다
    exercise: Literal["SQUAT"] | None = None
    features: FeaturesCfg
    squat: SquatCfg
    #: 없으면 그 카탈로그 버전으로는 해당 종목을 판정할 수 없다 (ConfigError)
    pushup: PushupCfg | None = None
    situp: SitupCfg | None = None
    lunge: LungeCfg | None = None
    inverted_shoulder_press: InvertedShoulderPressCfg | None = None
    glute_bridge: GluteBridgeCfg | None = None
    side_leg_lift: SideLegLiftCfg | None = None
    high_knee: HighKneeCfg | None = None
    mountain_climber: MountainClimberCfg | None = None
    superman: SupermanCfg | None = None
    donkey_kick: DonkeyKickCfg | None = None
    #: 없으면 어느 종목도 자세를 확인하지 않는다 (cat_2026-11-17 전 카탈로그)
    posture: PostureCfg | None = None
    liveness: LivenessCfg
    confidence: ConfidenceCfg
    form_tags: FormTagsCfg
    anomaly: AnomalyCfg
    #: 종목별 이상 징후 덮어쓰기 (D-87). 없으면 모든 종목이 `anomaly`를 쓴다 (cat_2026-11-23 전)
    anomaly_by_exercise: AnomalyByExerciseCfg | None = None
    recount: RecountCfg

    @model_validator(mode="after")
    def _anomaly_overrides(self) -> EngineConfig:
        if self.anomaly_by_exercise is not None:
            for key in AnomalyByExerciseCfg.model_fields:
                override = getattr(self.anomaly_by_exercise, key)
                if override is not None:
                    try:
                        merge_anomaly(self.anomaly, override)
                    except ValidationError as exc:
                        raise ValueError(f"anomaly_by_exercise.{key} 검증 실패: {exc}") from exc
        return self


class Catalog:
    """카탈로그 원본 + 모델 계열별 덮어쓰기."""

    def __init__(self, base: EngineConfig, overrides: dict[str, dict[str, Any]]) -> None:
        self.base = base
        self.version = base.catalog_version
        self._overrides = overrides
        self._resolved: dict[str, EngineConfig] = {}
        # 덮어쓰기도 로드 시점에 전부 검증한다
        for family in overrides:
            self.for_model(family)

    def for_model(self, family: str) -> EngineConfig:
        """모델 계열(`mediapipe`, `movenet`)의 덮어쓰기를 적용한 설정."""
        if family not in self._overrides:
            return self.base
        if family not in self._resolved:
            merged = _deep_merge(self.base.model_dump(), self._overrides[family])
            try:
                self._resolved[family] = EngineConfig.model_validate(merged)
            except ValidationError as exc:
                raise ConfigError(f"model_overrides.{family} 검증 실패: {exc}") from exc
        return self._resolved[family]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, val in override.items():
        if key not in out:
            raise ConfigError(f"model_overrides에 알 수 없는 키: {key}")
        if isinstance(val, dict) and isinstance(out[key], dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def parse_catalog(data: dict[str, Any]) -> Catalog:
    """YAML에서 읽은 dict를 검증해 Catalog로 만든다."""
    if not isinstance(data, dict):
        raise ConfigError("카탈로그 최상위는 매핑이어야 함")
    body = dict(data)
    overrides = body.pop("model_overrides", None) or {}
    if not isinstance(overrides, dict) or not all(isinstance(v, dict) for v in overrides.values()):
        raise ConfigError("model_overrides는 {계열: {키: 값}} 형식이어야 함")
    try:
        base = EngineConfig.model_validate(body)
    except ValidationError as exc:
        raise ConfigError(f"카탈로그 검증 실패: {exc}") from exc
    return Catalog(base, overrides)


def load_catalog(version: str, catalog_dir: Path | None = None) -> Catalog:
    """`<catalog_dir>/<version>.yaml`을 읽어 검증한다.

    파일이 없으면 `CatalogNotFoundError`, 내용이 틀리면 `ConfigError`.
    """
    if not _VERSION_RE.match(version):
        raise CatalogNotFoundError(f"잘못된 catalogVersion 형식: {version}")
    directory = catalog_dir or DEFAULT_CATALOG_DIR
    path = directory / f"{version}.yaml"
    if not path.is_file():
        raise CatalogNotFoundError(f"카탈로그 없음: {version}", {"catalogVersion": version})
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    catalog = parse_catalog(data)
    if catalog.version != version:
        raise ConfigError(f"파일 이름({version})과 catalog_version({catalog.version})이 다름")
    return catalog


def list_catalog_versions(catalog_dir: Path | None = None) -> list[str]:
    """사용 가능한 catalogVersion 목록 (이름순)."""
    directory = catalog_dir or DEFAULT_CATALOG_DIR
    return sorted(p.stem for p in directory.glob("cat_*.yaml"))
