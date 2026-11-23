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
from rep_engine.config import (
    AnomalyCfg,
    CalfRaiseCfg,
    EngineConfig,
    FlexionCfg,
    PushupCfg,
    TorsoRangeCfg,
    merge_anomaly,
)
from rep_engine.counters import base as counters
from rep_engine.errors import UnsupportedExerciseError
from rep_engine.features.calf import CalfFeatureExtractor, calf_quality
from rep_engine.features.chain import (
    BIRD_DOG_LEFT_SPEC,
    BIRD_DOG_RIGHT_SPEC,
    BOTH_LEGS_QUALITY_SPEC,
    DONKEY_KICK_SPEC,
    GLUTE_BRIDGE_SPEC,
    HIGH_KNEE_LEFT_SPEC,
    HIGH_KNEE_RIGHT_SPEC,
    INVERTED_SHOULDER_PRESS_SPEC,
    LUNGE_SPEC,
    MOUNTAIN_CLIMBER_LEFT_SPEC,
    MOUNTAIN_CLIMBER_RIGHT_SPEC,
    PUSHUP_SPEC,
    REVERSE_CRUNCH_SPEC,
    SIDE_LEG_LIFT_SPEC,
    SIDE_LUNGE_LEFT_SPEC,
    SIDE_LUNGE_RIGHT_SPEC,
    SITUP_SPEC,
    SUPERMAN_SPEC,
    AlternatingFeatureExtractor,
    AlternatingFeatures,
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
    BirdDogRepEvent,
    CalfRaiseRepEvent,
    DonkeyKickRepEvent,
    ExerciseType,
    GluteBridgeRepEvent,
    HighKneeRepEvent,
    InvertedShoulderPressRepEvent,
    LungeRepEvent,
    MountainClimberRepEvent,
    PushupRepEvent,
    RepEvent,
    ReverseCrunchRepEvent,
    SideLegLiftRepEvent,
    SideLungeRepEvent,
    SitupRepEvent,
    SupermanRepEvent,
)
from rep_engine.summary import (
    bird_dog_pose_summary,
    calf_raise_pose_summary,
    donkey_kick_pose_summary,
    glute_bridge_pose_summary,
    high_knee_pose_summary,
    inverted_shoulder_press_pose_summary,
    lunge_pose_summary,
    mountain_climber_pose_summary,
    pose_summary,
    pushup_pose_summary,
    reverse_crunch_pose_summary,
    side_leg_lift_pose_summary,
    side_lunge_pose_summary,
    situp_pose_summary,
    superman_pose_summary,
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
    #: 종목별 이상 징후 기준 (D-87). None이면 카탈로그 공통 `anomaly`를 쓴다
    anomaly: AnomalyCfg | None = None


def _flexion_rest(cfg: FlexionCfg) -> Callable[[ChainFeatures], bool]:
    def is_rest(f: ChainFeatures) -> bool:
        return f.angle_raw is not None and f.angle_raw >= cfg.rest_angle

    return is_rest


def _anomaly(cfg: EngineConfig, key: str) -> AnomalyCfg | None:
    """종목별 이상 징후 기준 (D-87). 덮어쓰기가 없으면 None(공통 기준 그대로)."""
    if cfg.anomaly_by_exercise is None:
        return None
    override = getattr(cfg.anomaly_by_exercise, key)
    return None if override is None else merge_anomaly(cfg.anomaly, override)


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
        anomaly=_anomaly(cfg, key),
    )


def _alternating_kit(
    exercise: ExerciseType,
    cfg: EngineConfig,
    key: str,
    specs: tuple[ChainSpec, ChainSpec],
    summarize: Callable[[Sequence[AnyRepEvent]], AnyPoseSummary],
    quality: QualityFn | None = None,
) -> ExerciseKit:
    """좌우를 번갈아 하는 종목(D-83): 쪽마다 특징을 따로 뽑아 판정기에 함께 넘긴다.

    `quality`를 주지 않으면 두 쪽 판정 값이 모두 계산되어야 유효 프레임이다 (`_both_sides_quality`).
    """
    section = _section(cfg, exercise, key)
    rng = _posture_range(cfg, key)

    def is_rest(f: AlternatingFeatures) -> bool:
        return all(
            leg.angle_raw is not None and leg.angle_raw >= section.rest_angle
            for leg in (f.left, f.right)
        )

    return ExerciseKit(
        extractor=AlternatingFeatureExtractor(cfg.features, specs[0], specs[1], rng),
        counter=counters.make_counter(exercise, cfg),
        quality=_with_posture(quality or _both_sides_quality(specs), rng),
        is_rest=is_rest,
        summarize=summarize,
        anomaly=_anomaly(cfg, key),
    )


def _both_sides_quality(specs: tuple[ChainSpec, ChainSpec]) -> QualityFn:
    """확신도용 프레임 품질: 두 쪽 판정 값이 모두 계산되어야 유효, 가시도는 두 쪽 평균."""
    left, right = chain_quality(specs[0]), chain_quality(specs[1])

    def quality(frame: SkeletonFrame, min_visibility: float) -> tuple[bool, float | None]:
        ok_l, vis_l = left(frame, min_visibility)
        ok_r, vis_r = right(frame, min_visibility)
        if not (ok_l and ok_r) or vis_l is None or vis_r is None:
            return False, None
        return True, (vis_l + vis_r) / 2.0

    return quality


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
    if exercise == "SIDE_LEG_LIFT":
        return _chain_kit(
            exercise,
            cfg,
            "side_leg_lift",
            SIDE_LEG_LIFT_SPEC,
            lambda reps: side_leg_lift_pose_summary(
                [e for e in reps if isinstance(e, SideLegLiftRepEvent)], ft
            ),
        )
    if exercise == "HIGH_KNEE":
        return _alternating_kit(
            exercise,
            cfg,
            "high_knee",
            (HIGH_KNEE_LEFT_SPEC, HIGH_KNEE_RIGHT_SPEC),
            lambda reps: high_knee_pose_summary(
                [e for e in reps if isinstance(e, HighKneeRepEvent)], ft
            ),
            chain_quality(BOTH_LEGS_QUALITY_SPEC),
        )
    if exercise == "MOUNTAIN_CLIMBER":
        return _alternating_kit(
            exercise,
            cfg,
            "mountain_climber",
            (MOUNTAIN_CLIMBER_LEFT_SPEC, MOUNTAIN_CLIMBER_RIGHT_SPEC),
            lambda reps: mountain_climber_pose_summary(
                [e for e in reps if isinstance(e, MountainClimberRepEvent)], ft
            ),
            chain_quality(BOTH_LEGS_QUALITY_SPEC),
        )
    if exercise == "SUPERMAN":
        return _chain_kit(
            exercise,
            cfg,
            "superman",
            SUPERMAN_SPEC,
            lambda reps: superman_pose_summary(
                [e for e in reps if isinstance(e, SupermanRepEvent)], ft
            ),
        )
    if exercise == "DONKEY_KICK":
        return _chain_kit(
            exercise,
            cfg,
            "donkey_kick",
            DONKEY_KICK_SPEC,
            lambda reps: donkey_kick_pose_summary(
                [e for e in reps if isinstance(e, DonkeyKickRepEvent)], ft
            ),
        )
    if exercise == "REVERSE_CRUNCH":
        return _chain_kit(
            exercise,
            cfg,
            "reverse_crunch",
            REVERSE_CRUNCH_SPEC,
            lambda reps: reverse_crunch_pose_summary(
                [e for e in reps if isinstance(e, ReverseCrunchRepEvent)], ft
            ),
        )
    if exercise == "SIDE_LUNGE":
        return _alternating_kit(
            exercise,
            cfg,
            "side_lunge",
            (SIDE_LUNGE_LEFT_SPEC, SIDE_LUNGE_RIGHT_SPEC),
            lambda reps: side_lunge_pose_summary(
                [e for e in reps if isinstance(e, SideLungeRepEvent)], ft
            ),
        )
    if exercise == "BIRD_DOG":
        return _alternating_kit(
            exercise,
            cfg,
            "bird_dog",
            (BIRD_DOG_LEFT_SPEC, BIRD_DOG_RIGHT_SPEC),
            lambda reps: bird_dog_pose_summary(
                [e for e in reps if isinstance(e, BirdDogRepEvent)], ft
            ),
        )
    return _calf_kit(cfg)


def _calf_kit(cfg: EngineConfig) -> ExerciseKit:
    """카프 레이즈 (D-92): 바닥 위치를 기억하는 전용 특징 추출기를 쓴다."""
    section = _section(cfg, "CALF_RAISE", "calf_raise")
    assert isinstance(section, CalfRaiseCfg)
    rng = _posture_range(cfg, "calf_raise")
    ft = cfg.form_tags
    return ExerciseKit(
        extractor=CalfFeatureExtractor(cfg.features, section.floor_window_ms, rng),
        counter=counters.make_counter("CALF_RAISE", cfg),
        quality=_with_posture(calf_quality, rng),
        is_rest=_flexion_rest(section),
        summarize=lambda reps: calf_raise_pose_summary(
            [e for e in reps if isinstance(e, CalfRaiseRepEvent)], ft
        ),
        anomaly=_anomaly(cfg, "calf_raise"),
    )
