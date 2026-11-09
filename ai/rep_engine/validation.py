"""업로드 메타·청크 검증 (SPEC 3.2, 9.1 1~2단계)."""

from __future__ import annotations

from collections.abc import Sequence

from rep_engine.adapters import PoseAdapter, adapter_for_model_version
from rep_engine.errors import ChunkValidationError, MissingChunksError
from rep_engine.schemas import CHUNK_SPEC, Chunk, ChunkSpec, Frame, SessionMeta


def chunk_size_bytes(chunk: Chunk) -> int:
    """청크의 camelCase JSON 직렬화 크기(바이트)."""
    return len(chunk.to_json().encode("utf-8"))


def validate_chunk_limits(chunk: Chunk, spec: ChunkSpec = CHUNK_SPEC) -> None:
    """청크 1개의 프레임 수·크기 제한을 검사한다."""
    if len(chunk.frames) > spec.max_frames:
        raise ChunkValidationError(
            f"seq={chunk.seq}: 프레임 수 {len(chunk.frames)} > {spec.max_frames}",
            {"seq": chunk.seq},
        )
    size = chunk_size_bytes(chunk)
    if size > spec.max_bytes:
        raise ChunkValidationError(
            f"seq={chunk.seq}: 청크 크기 {size}B > {spec.max_bytes}B", {"seq": chunk.seq}
        )


def validate_time_order(frames: Sequence[Frame]) -> None:
    """t가 엄격히 증가하는지(역순·중복 금지) 검사한다."""
    prev: int | None = None
    for fr in frames:
        if prev is not None and fr.t <= prev:
            raise ChunkValidationError(f"프레임 시각이 증가하지 않음: {prev} → {fr.t}", {"t": fr.t})
        prev = fr.t


def assemble_frames(
    meta: SessionMeta, chunks: Sequence[Chunk], spec: ChunkSpec = CHUNK_SPEC
) -> tuple[PoseAdapter, list[Frame]]:
    """청크 완결성·크기·시각 순서·모델별 관절 형식을 검사하고 프레임을 이어 붙인다.

    Returns: (선택된 어댑터, 시각순 프레임 목록)
    Raises: MissingChunksError, ChunkValidationError, UnknownModelError
    """
    adapter = adapter_for_model_version(meta.device.model_version)
    by_seq: dict[int, Chunk] = {}
    for ch in chunks:
        if ch.session_id != meta.session_id:
            raise ChunkValidationError(f"seq={ch.seq}: sessionId가 메타와 다름", {"seq": ch.seq})
        if ch.seq in by_seq:
            raise ChunkValidationError(f"seq={ch.seq} 중복", {"seq": ch.seq})
        by_seq[ch.seq] = ch
    if by_seq:
        last = max(by_seq)
        missing = [s for s in range(last + 1) if s not in by_seq]
        if missing:
            raise MissingChunksError(missing)
    frames: list[Frame] = []
    for seq in sorted(by_seq):
        ch = by_seq[seq]
        validate_chunk_limits(ch, spec)
        for fr in ch.frames:
            adapter.validate_frame(fr)
        frames.extend(ch.frames)
    validate_time_order(frames)
    return adapter, frames
