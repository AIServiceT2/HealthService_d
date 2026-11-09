import pytest

from rep_engine.errors import ChunkValidationError, MissingChunksError, UnknownModelError
from rep_engine.schemas import Chunk, ChunkSpec, SessionMeta
from rep_engine.validation import assemble_frames, chunk_size_bytes
from tests.helpers import meta_dict, raw_landmarks


def _chunk(seq: int, ts: list[int], sid: str = "s1") -> Chunk:
    return Chunk.model_validate(
        {
            "sessionId": sid,
            "seq": seq,
            "frames": [{"t": t, "landmarks": raw_landmarks()} for t in ts],
        }
    )


META = SessionMeta.model_validate(meta_dict())


def test_assemble_in_seq_order() -> None:
    adapter, frames = assemble_frames(META, [_chunk(1, [200, 266]), _chunk(0, [0, 66])])
    assert adapter.family == "mediapipe"
    assert [f.t for f in frames] == [0, 66, 200, 266]


def test_missing_seq_lists_exact_gaps() -> None:
    with pytest.raises(MissingChunksError) as ei:
        assemble_frames(META, [_chunk(0, [0]), _chunk(3, [300]), _chunk(5, [500])])
    assert ei.value.missing_seq == [1, 2, 4]
    assert ei.value.details == {"missingSeq": [1, 2, 4]}


def test_duplicate_seq_and_wrong_session() -> None:
    with pytest.raises(ChunkValidationError, match="중복"):
        assemble_frames(META, [_chunk(0, [0]), _chunk(0, [10])])
    with pytest.raises(ChunkValidationError, match="sessionId"):
        assemble_frames(META, [_chunk(0, [0], sid="other")])


def test_time_must_increase() -> None:
    with pytest.raises(ChunkValidationError, match="증가"):
        assemble_frames(META, [_chunk(0, [0, 66, 66])])
    with pytest.raises(ChunkValidationError, match="증가"):
        assemble_frames(META, [_chunk(0, [0, 100]), _chunk(1, [50])])


def test_frame_and_byte_limits() -> None:
    ch = _chunk(0, list(range(0, 400 * 66, 66)))
    with pytest.raises(ChunkValidationError, match="프레임 수"):
        assemble_frames(META, [ch])
    small = _chunk(0, [0, 66])
    spec = ChunkSpec(max_frames=300, max_bytes=chunk_size_bytes(small) - 1)
    with pytest.raises(ChunkValidationError, match="크기"):
        assemble_frames(META, [small], spec)


def test_unknown_model_in_meta() -> None:
    meta = SessionMeta.model_validate(meta_dict(model_version="yolo-pose"))
    with pytest.raises(UnknownModelError):
        assemble_frames(meta, [_chunk(0, [0])])


def test_empty_chunks_ok() -> None:
    _, frames = assemble_frames(META, [])
    assert frames == []
