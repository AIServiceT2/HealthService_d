"""종목별 부품 묶음: 특징 추출기 · 렙 판정기 · 확신도 프레임 품질 · 쉬는 자세 · 자세 요약.

세션 실행기(`session.py`)는 `exerciseType`으로 이 묶음을 받아 쓰고, 종목을 직접 알지 않는다.
카탈로그에 그 종목 섹션(pushup/situp)이 없으면 `UnsupportedExerciseError`(API 400).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from rep_engine.adapters import SkeletonFrame
from rep_engine.anomaly import squat_rest
from rep_engine.confidence import QualityFn
from rep_engine.config import EngineConfig, FlexionCfg
from rep_engine.counters import base as counters
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.chain import (
    PUSHUP_SPEC,
    SITUP_SPEC,
    ChainFeatureExtractor,
    ChainFeatures,
    ChainSpec,
    chain_quality,
)
from rep_engine.features.extractor import FeatureExtractor, frame_quality
from rep_engine.schemas import (
    AnyPoseSummary,
    AnyRepEvent,
    ExerciseType,
    PushupRepEvent,
    RepEvent,
    SitupRepEvent,
)
from rep_engine.summary import pose_summary, pushup_pose_summary, situp_pose_summary


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


def _chain_kit(
    exercise: ExerciseType,
    cfg: EngineConfig,
    section: FlexionCfg,
    spec: ChainSpec,
    summarize: Callable[[Sequence[AnyRepEvent]], AnyPoseSummary],
) -> ExerciseKit:
    return ExerciseKit(
        extractor=ChainFeatureExtractor(cfg.features, spec),
        counter=counters.make_counter(exercise, cfg),
        quality=chain_quality(spec),
        is_rest=_flexion_rest(section),
        summarize=summarize,
    )


def make_kit(exercise: ExerciseType, cfg: EngineConfig) -> ExerciseKit:
    """종목 부품 묶음을 만든다. 카탈로그에 종목 기준이 없으면 UnsupportedExerciseError."""
    if exercise == "SQUAT":
        return ExerciseKit(
            extractor=FeatureExtractor(cfg.features, cfg.squat.stand_angle),
            counter=counters.make_counter(exercise, cfg),
            quality=frame_quality,
            is_rest=squat_rest(cfg.squat.stand_angle),
            summarize=lambda reps: pose_summary(
                [e for e in reps if isinstance(e, RepEvent)], cfg.form_tags
            ),
        )
    if exercise == "PUSHUP":
        pushup = cfg.pushup
        if pushup is None:
            raise UnsupportedExerciseError(
                f"카탈로그 {cfg.catalog_version}에 pushup 기준이 없음",
                {"catalogVersion": cfg.catalog_version, "exerciseType": "PUSHUP"},
            )
        return _chain_kit(
            exercise,
            cfg,
            pushup,
            PUSHUP_SPEC,
            lambda reps: pushup_pose_summary(
                [e for e in reps if isinstance(e, PushupRepEvent)], cfg.form_tags, pushup
            ),
        )
    situp = cfg.situp
    if situp is None:
        raise UnsupportedExerciseError(
            f"카탈로그 {cfg.catalog_version}에 situp 기준이 없음",
            {"catalogVersion": cfg.catalog_version, "exerciseType": "SITUP"},
        )
    return _chain_kit(
        exercise,
        cfg,
        situp,
        SITUP_SPEC,
        lambda reps: situp_pose_summary(
            [e for e in reps if isinstance(e, SitupRepEvent)], cfg.form_tags
        ),
    )
