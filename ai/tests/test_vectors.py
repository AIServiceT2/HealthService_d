"""저장소의 테스트 벡터가 지금 엔진 결과와 같은지 확인한다.

엔진·카탈로그를 바꾸면 벡터를 다시 만들어야 한다 (python -m tools.make_test_vectors).
"""

import json
from pathlib import Path

import pytest

from rep_engine import ENGINE_VERSION
from rep_engine.schemas import Chunk, SessionMeta
from rep_engine.session import run_session

VECTOR_DIR = Path(__file__).resolve().parent.parent / "test_vectors"
VECTORS = sorted(p for p in VECTOR_DIR.glob("*.json") if p.name != "index.json")


def test_vectors_exist_and_indexed() -> None:
    assert len(VECTORS) >= 10
    index = json.loads((VECTOR_DIR / "index.json").read_text(encoding="utf-8"))
    assert index["engineVersion"] == ENGINE_VERSION
    assert {v["name"] for v in index["vectors"]} == {p.stem for p in VECTORS}


@pytest.mark.parametrize("path", VECTORS, ids=[p.stem for p in VECTORS])
def test_vector_matches_engine(path: Path) -> None:
    body = json.loads(path.read_text(encoding="utf-8"))
    meta = SessionMeta.model_validate(body["meta"])
    chunks = [Chunk.model_validate(c) for c in body["chunks"]]
    assert run_session(meta, chunks).to_dict() == body["expected"], (
        "엔진 결과가 벡터와 다름 — 의도한 변경이면 python -m tools.make_test_vectors로 재생성"
    )
