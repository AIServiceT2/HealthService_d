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


class PushupCfg(FlexionCfg):
    """푸시업. 판정 각도 = 팔꿈치 내각(어깨–팔꿈치–손목)."""

    #: 인정 렙 평균 몸통 이탈(180 − 어깨–엉덩이–발목 내각)이 이 값을 넘으면 BODY_LINE_BROKEN
    body_line_dev_deg: float = Field(ge=0)
    #: 어깨–발목(안 보이면 어깨–엉덩이) 선이 화면 수평선에서 이 각도 이내일 때만 렙으로 셈 (D-71)
    max_torso_tilt_deg: float = Field(ge=0, le=90)


class SitupCfg(FlexionCfg):
    """윗몸 일으키기. 판정 각도 = 상체 각도(어깨–엉덩이–발목 내각, 180 − 상체가 들린 각도).

    상체 각도 기준(`depth_accept_angle`)과 엉덩이 각도 기준(`hip_accept_angle`)을 **둘 다** 넘어야
    인정한다 (D-70).
    """

    #: 렙 동안 엉덩이 내각(어깨–엉덩이–무릎) 최저값이 이 값 이하여야 인정
    hip_accept_angle: float = Field(gt=0, lt=180)


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
    liveness: LivenessCfg
    confidence: ConfidenceCfg
    form_tags: FormTagsCfg
    anomaly: AnomalyCfg
    recount: RecountCfg


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
