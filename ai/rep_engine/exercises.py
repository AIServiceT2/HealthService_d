"""종목별 부품 묶음: 특징 추출기 · 렙 판정기 · 확신도 프레임 품질 · 쉬는 자세 · 자세 요약.

세션 실행기(`session.py`)는 `exerciseType`으로 이 묶음을 받아 쓰고, 종목을 직접 알지 않는다.
카탈로그에 그 종목 섹션(pushup/situp/lunge/…)이 없으면 `UnsupportedExerciseError`(API 400).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from rep_engine.adapters import SkeletonFrame
from rep_engine.anomaly import squat_rest
from rep_engine.confidence import QualityFn
from rep_engine.config import EngineConfig, FlexionCfg, PushupCfg, TorsoRangeCfg
from rep_engine.counters import base as counters
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import (
    GLUTE_BRIDGE_SPEC,
    INVERTED_SHOULDER_PRESS_SPEC,
    LUNGE_SPEC,
    PUSHUP_SPEC,
    SIDE_LEG_LIFT_SPEC,
    SITUP_SPEC,
    ChainFeatureExtractor,
    ChainFeatures,
    ChainSpec,
    chain_quality,
)
from rep_engine.features.extractor import FeatureExtractor, frame_quality
from rep_engine.features.posture import posture_ok
from rep_engine.schemas import (
    AnyPoseSummary,
    AnyRepEvent,
    ExerciseType,
    GluteBridgeRepEvent,
    InvertedShoulderPressRepEvent,
    LungeRepEvent,
    PushupRepEvent,
    RepEvent,
    SideLegLiftRepEvent,
    SitupRepEvent,
)
from rep_engine.summary import (
    glute_bridge_pose_summary,
    inverted_shoulder_press_pose_summary,
    lunge_pose_summary,
    pose_summary,
    pushup_pose_summary,
    side_leg_lift_pose_summary,
    situp_pose_summary,
)


class Extractor(Protocol):
    """스트리밍 특징 추출기 (FeatureExtractor·ChainFeatureExtractor)."""

    def update(self, frame: SkeletonFrame) -> Any: ...


@dataclass(frozen=True)
class ExerciseKit:
    extractor: Extractor
    counter: counters.ExerciseCounter[Any]
    quality: QualityFn
    is_rest: Callable[[Any], bool]
    summarize: Callable[[Sequence[AnyRepEvent]], AnyPoseSummary]


def _flexion_rest(cfg: FlexionCfg) -> Callable[[ChainFeatures], bool]:
    def is_rest(f: ChainFeatures) -> bool:
        return f.angle_raw is not None and f.angle_raw >= cfg.rest_angle

    return is_rest


def _posture_range(cfg: EngineConfig, key: str) -> TorsoRangeCfg | None:
    """종목의 자세 확인 범위 (D-75). 카탈로그에 없으면 None(확인 안 함)."""
    if cfg.posture is None:
        return None
    rng = getattr(cfg.posture, key)
    assert rng is None or isinstance(rng, TorsoRangeCfg)
    return rng


def _with_posture(quality: QualityFn, rng: TorsoRangeCfg | None) -> QualityFn:
    """확신도용 프레임 품질에도 자세 확인을 건다 (자세가 틀린 프레임은 유효 프레임이 아님)."""
    if rng is None:
        return quality

    def checked(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
        if frame.joints is None or not posture_ok(frame.joints, min_visibility, rng):
            return False, None
        return quality(frame, min_visibility)

    return checked


def _chain_kit(
    exercise: ExerciseType,
    cfg: EngineConfig,
    key: str,
    spec: ChainSpec,
    summarize: Callable[[Sequence[AnyRepEvent]], AnyPoseSummary],
) -> ExerciseKit:
    section = _section(cfg, exercise, key)
    rng = _posture_range(cfg, key)
    return ExerciseKit(
        extractor=ChainFeatureExtractor(cfg.features, spec, rng),
        counter=counters.make_counter(exercise, cfg),
        quality=_with_posture(chain_quality(spec), rng),
        is_rest=_flexion_rest(section),
        summarize=summarize,
    )


def _section(cfg: EngineConfig, exercise: ExerciseType, key: str) -> FlexionCfg:
    """카탈로그의 종목 섹션. 없으면 UnsupportedExerciseError (API 400)."""
    section = getattr(cfg, key)
    if section is None:
        raise UnsupportedExerciseError(
            f"카탈로그 {cfg.catalog_version}에 {key} 기준이 없음",
            {"catalogVersion": cfg.catalog_version, "exerciseType": exercise},
        )
    assert isinstance(section, FlexionCfg)
    return section


def make_kit(exercise: ExerciseType, cfg: EngineConfig) -> ExerciseKit:
    """종목 부품 묶음을 만든다. 카탈로그에 종목 기준이 없으면 UnsupportedExerciseError."""
    ft = cfg.form_tags
    if exercise == "SQUAT":
        rng = _posture_range(cfg, "squat")
        return ExerciseKit(
            extractor=FeatureExtractor(cfg.features, cfg.squat.stand_angle, rng),
            counter=counters.make_counter(exercise, cfg),
            quality=_with_posture(frame_quality, rng),
            is_rest=squat_rest(cfg.squat.stand_angle),
            summarize=lambda reps: pose_summary([e for e in reps if isinstance(e, RepEvent)], ft),
        )
    if exercise == "PUSHUP":
        pushup = _section(cfg, exercise, "pushup")
        assert isinstance(pushup, PushupCfg)
        return _chain_kit(
            exercise,
            cfg,
            "pushup",
            PUSHUP_SPEC,
            lambda reps: pushup_pose_summary(
                [e for e in reps if isinstance(e, PushupRepEvent)], ft, pushup
            ),
        )
    if exercise == "SITUP":
        return _chain_kit(
            exercise,
            cfg,
            "situp",
            SITUP_SPEC,
            lambda reps: situp_pose_summary([e for e in reps if isinstance(e, SitupRepEvent)], ft),
        )
    if exercise == "LUNGE":
        return _chain_kit(
            exercise,
            cfg,
            "lunge",
            LUNGE_SPEC,
            lambda reps: lunge_pose_summary([e for e in reps if isinstance(e, LungeRepEvent)], ft),
        )
    if exercise == "INVERTED_SHOULDER_PRESS":
        return _chain_kit(
            exercise,
            cfg,
            "inverted_shoulder_press",
            INVERTED_SHOULDER_PRESS_SPEC,
            lambda reps: inverted_shoulder_press_pose_summary(
                [e for e in reps if isinstance(e, InvertedShoulderPressRepEvent)], ft
            ),
        )
    if exercise == "GLUTE_BRIDGE":
        return _chain_kit(
            exercise,
            cfg,
            "glute_bridge",
            GLUTE_BRIDGE_SPEC,
            lambda reps: glute_bridge_pose_summary(
                [e for e in reps if isinstance(e, GluteBridgeRepEvent)], ft
            ),
        )
    return _chain_kit(
        exercise,
        cfg,
        "side_leg_lift",
        SIDE_LEG_LIFT_SPEC,
        lambda reps: side_leg_lift_pose_summary(
            [e for e in reps if isinstance(e, SideLegLiftRepEvent)], ft
        ),
    )
