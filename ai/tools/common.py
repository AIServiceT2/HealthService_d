"""도구 공용: 세션 JSON 읽기·쓰기, 청크 나누기, 로깅.

세션 파일 형식: `{"meta": SessionMeta, "chunks": [Chunk, ...], "expected"?: SessionResult}`
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rep_engine.schemas import CHUNK_SPEC, Chunk, ChunkSpec, Frame, SessionMeta
from rep_engine.validation import validate_chunk_limits

AI_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = AI_ROOT / "data"
REPORTS_DIR = AI_ROOT / "reports"
MODELS_DIR = AI_ROOT / "models"

#: Chunk JSON에서 frames 배열 밖의 고정 부분 여유 (sessionId·seq 키 등)
_CHUNK_ENVELOPE_BYTES = 256


def setup_logging(verbose: bool = False) -> logging.Logger:
    """표준 출력 로깅 (도구 공통)."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger("ai.tools")


def split_chunks(
    session_id: str, frames: Sequence[Frame], spec: ChunkSpec = CHUNK_SPEC
) -> list[Chunk]:
    """프레임을 프레임 수·바이트 제한(둘 다)을 지키는 청크로 나눈다 (DECISIONS D-06)."""
    limit = spec.max_bytes - _CHUNK_ENVELOPE_BYTES - len(session_id.encode())
    chunks: list[Chunk] = []
    cur: list[Frame] = []
    size = 0
    for fr in frames:
        fsize = len(fr.to_json().encode()) + 1  # 쉼표
        if cur and (len(cur) >= spec.max_frames or size + fsize > limit):
            chunks.append(Chunk(session_id=session_id, seq=len(chunks), frames=cur))
            cur, size = [], 0
        cur.append(fr)
        size += fsize
    if cur:
        chunks.append(Chunk(session_id=session_id, seq=len(chunks), frames=cur))
    for ch in chunks:
        validate_chunk_limits(ch, spec)
    return chunks


def save_session(
    path: Path, meta: SessionMeta, chunks: Sequence[Chunk], extra: dict[str, Any] | None = None
) -> None:
    """세션 JSON 저장 (camelCase)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {"meta": meta.to_dict(), "chunks": [c.to_dict() for c in chunks]}
    body.update(extra or {})
    path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def load_session(path: Path) -> tuple[SessionMeta, list[Chunk], dict[str, Any]]:
    """세션 JSON 읽기. 세 번째 값은 meta·chunks 외 나머지 키."""
    body = json.loads(path.read_text(encoding="utf-8"))
    meta = SessionMeta.model_validate(body.pop("meta"))
    chunks = [Chunk.model_validate(c) for c in body.pop("chunks")]
    return meta, chunks, body


def all_frames(chunks: Sequence[Chunk]) -> list[Frame]:
    return [f for c in sorted(chunks, key=lambda c: c.seq) for f in c.frames]
