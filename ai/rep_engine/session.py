"""세션 단위 실행기 (SPEC 9.1). 스트리밍(웹캠·기기)과 배치(서버 재계산)가 같은 코드를 쓴다.

처리 순서:
1. (배치만) 청크 완결성·크기·시각 순서·관절 형식 검사 → 프레임 이어 붙이기
2. `catalogVersion` 설정 로드 + 모델 계열 덮어쓰기 적용 (세션 도중 기준값은 바뀌지 않음)
3. 프레임마다: 어댑터(공통 골격) → 무작위 동작 확인(issuedAtT~expiresAtT)
   → 렙 판정. 렙 판정은 무작위 동작이 끝난 뒤의 프레임만 쓴다 (DECISIONS D-34):
   통과 → passedAtT 이후, 실패 → expiresAtT 이후, 확인 없음 → 처음부터.
4. 끝나면 확신도 → 자세 요약 → 이상 징후.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from rep_engine import ENGINE_VERSION
from rep_engine.adapters import PoseAdapter, SkeletonFrame, adapter_for_model_version
from rep_engine.anomaly import detect_anomalies
from rep_engine.confidence import compute_confidence
from rep_engine.config import Catalog, EngineConfig, load_catalog
from rep_engine.errors import ConfigError
from rep_engine.exercises import make_kit
from rep_engine.liveness import LivenessEvaluator
from rep_engine.schemas import (
    AnyRepEvent,
    Chunk,
    Frame,
    LivenessResult,
    LivenessStatus,
    SessionMeta,
    SessionResult,
)
from rep_engine.validation import assemble_frames


class SessionRunner:
    """세션 1개의 스트리밍 실행기. `push`로 프레임을 넣고 `finish`로 결과를 받는다."""

    def __init__(
        self, meta: SessionMeta, catalog: Catalog, adapter: PoseAdapter | None = None
    ) -> None:
        if catalog.version != meta.catalog_version:
            raise ConfigError(
                f"catalogVersion 불일치: 메타 {meta.catalog_version}, 설정 {catalog.version}"
            )
        self.meta = meta
        self.adapter = adapter or adapter_for_model_version(meta.device.model_version)
        self.cfg: EngineConfig = catalog.for_model(self.adapter.family)
        self.kit = make_kit(meta.exercise_type, self.cfg)
        self.counter = self.kit.counter
        self._extractor = self.kit.extractor
        self._liveness = (
            LivenessEvaluator(meta.liveness, self.cfg.liveness, self.cfg.features.min_visibility)
            if meta.liveness is not None
            else None
        )
        self._liveness_result: LivenessResult | None = None
        self._count_after: int | None = None if meta.liveness is not None else -1
        self.skeletons: list[SkeletonFrame] = []
        self._count_frames: list[SkeletonFrame] = []
        #: 종목별 특징 (스쿼트: FrameFeatures, 푸시업·윗몸 일으키기: ChainFeatures)
        self._count_feats: list[Any] = []
        self.reps: list[AnyRepEvent] = []
        self.last_features: Any = None

    @property
    def liveness_result(self) -> LivenessResult | None:
        return self._liveness_result

    @property
    def features(self) -> list[Any]:
        """렙 판정 구간의 프레임 특징 (그래프·디버깅용, 읽기 전용으로 쓴다)."""
        return list(self._count_feats)

    @property
    def counting(self) -> bool:
        """렙 판정 단계인지 (무작위 동작 확인이 끝났거나 없음)."""
        return self._count_after is not None

    def _resolve_liveness(self, res: LivenessResult) -> None:
        self._liveness_result = res
        if res.status is LivenessStatus.PASSED and res.passed_at_t is not None:
            self._count_after = res.passed_at_t
        elif self.meta.liveness is not None:
            self._count_after = self.meta.liveness.expires_at_t

    def push(self, frame: Frame) -> list[AnyRepEvent]:
        """프레임 1개 처리. 이번 프레임에서 확정된 렙을 돌려준다."""
        sk = self.adapter.to_skeleton(
            frame, self.meta.image_width, self.meta.image_height, self.meta.mirrored
        )
        self.skeletons.append(sk)
        if self._liveness is not None and self._liveness_result is None:
            res = self._liveness.update(sk)
            if res is not None:
                self._resolve_liveness(res)
        if self._count_after is None or sk.t <= self._count_after:
            return []
        feats = self._extractor.update(sk)
        self.last_features = feats
        self._count_frames.append(sk)
        self._count_feats.append(feats)
        events = self.counter.update(feats)
        self.reps.extend(events)
        return events

    def finish(self) -> SessionResult:
        """입력 종료. 확신도·요약·이상 징후까지 계산한 결과."""
        if self._liveness is not None and self._liveness_result is None:
            self._resolve_liveness(self._liveness.finish())
        cfg = self.cfg
        conf = compute_confidence(
            self.skeletons,
            self.reps,
            self._liveness_result,
            cfg.confidence,
            cfg.features.min_visibility,
            self.kit.quality,
        )
        diag = math.hypot(self.meta.image_width, self.meta.image_height)
        anomalies = detect_anomalies(
            self._count_frames, self._count_feats, self.reps, cfg, diag, self.kit.is_rest
        )
        return SessionResult(
            engine_version=ENGINE_VERSION,
            catalog_version=cfg.catalog_version,
            reps=list(self.reps),
            recognized_reps=sum(1 for e in self.reps if e.accepted),
            attempted_reps=len(self.reps),
            liveness=self._liveness_result,
            ai_confidence=conf.ai_confidence,
            confidence_components=conf.components,
            pose_summary=self.kit.summarize(self.reps),
            anomalies=anomalies,
        )


def run_frames(meta: SessionMeta, frames: Iterable[Frame], catalog: Catalog) -> SessionResult:
    """이미 검증된 프레임 목록으로 실행 (배치 = 스트리밍 반복)."""
    runner = SessionRunner(meta, catalog)
    for fr in frames:
        runner.push(fr)
    return runner.finish()


def run_session(
    meta: SessionMeta,
    chunks: Sequence[Chunk],
    catalog: Catalog | None = None,
    catalog_dir: Path | None = None,
) -> SessionResult:
    """서버 재계산 진입점. 청크 검증 → 설정 로드 → 판정.

    Raises: MissingChunksError, ChunkValidationError, UnknownModelError,
            CatalogNotFoundError, ConfigError
    """
    adapter, frames = assemble_frames(meta, chunks)
    cat = catalog or load_catalog(meta.catalog_version, catalog_dir)
    runner = SessionRunner(meta, cat, adapter)
    for fr in frames:
        runner.push(fr)
    return runner.finish()
