import pytest
from pydantic import ValidationError

from rep_engine.schemas import Chunk, Frame, Landmark, LivenessChallenge, SessionMeta
from tests.helpers import meta_dict, raw_landmarks


def test_meta_parses_camel_case_and_dumps_camel_case() -> None:
    meta = SessionMeta.model_validate(meta_dict())
    assert meta.image_width == 720
    assert meta.device.model_version == "mediapipe-pose-full@0.10"
    out = meta.to_dict()
    assert "imageWidth" in out and "catalogVersion" in out
    assert out["device"]["modelVersion"] == "mediapipe-pose-full@0.10"


def test_meta_rejects_unknown_field_and_other_exercise() -> None:
    with pytest.raises(ValidationError):
        SessionMeta.model_validate(meta_dict(extra=1))
    with pytest.raises(ValidationError):
        SessionMeta.model_validate(meta_dict(exerciseType="PLANK"))


def test_landmark_ranges() -> None:
    Landmark(x=1.05, y=-0.02, z=None, visibility=0.0)  # 화면 밖 약간 허용
    with pytest.raises(ValidationError):
        Landmark(x=0.5, y=0.5, visibility=1.2)
    with pytest.raises(ValidationError):
        Landmark(x=5.0, y=0.5, visibility=0.5)


def test_frame_null_landmarks_and_chunk_roundtrip() -> None:
    ch = Chunk.model_validate(
        {
            "sessionId": "s1",
            "seq": 0,
            "frames": [{"t": 0, "landmarks": None}, {"t": 66, "landmarks": raw_landmarks()}],
        }
    )
    assert ch.frames[0].landmarks is None
    again = Chunk.model_validate_json(ch.to_json())
    assert again == ch


def test_negative_t_rejected() -> None:
    with pytest.raises(ValidationError):
        Frame(t=-1, landmarks=None)


def test_liveness_window_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        LivenessChallenge.model_validate(
            {"challengeId": "c", "action": "RAISE_LEFT_HAND", "issuedAtT": 10, "expiresAtT": 10}
        )
