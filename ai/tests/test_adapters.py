import pytest

from rep_engine.adapters import (
    MEDIAPIPE_ADAPTER,
    MOVENET_ADAPTER,
    adapter_for_model_version,
)
from rep_engine.errors import ChunkValidationError, UnknownModelError
from rep_engine.landmarks import MEDIAPIPE_INDEX, MOVENET_INDEX, Joint
from rep_engine.schemas import Frame, Landmark
from tests.helpers import raw_landmarks


@pytest.mark.parametrize(
    ("mv", "family"),
    [
        ("mediapipe-pose-lite@0.10", "mediapipe"),
        ("MediaPipe-Pose-Heavy", "mediapipe"),
        ("movenet-lightning@4", "movenet"),
        ("movenet", "movenet"),
    ],
)
def test_adapter_selection(mv: str, family: str) -> None:
    assert adapter_for_model_version(mv).family == family


@pytest.mark.parametrize("mv", ["blazepose", "movenetx", "", "openpose-1"])
def test_unknown_model(mv: str) -> None:
    with pytest.raises(UnknownModelError):
        adapter_for_model_version(mv)


def test_frame_length_and_face_checks() -> None:
    lms = raw_landmarks("mediapipe")
    MEDIAPIPE_ADAPTER.validate_frame(Frame.model_validate({"t": 0, "landmarks": lms}))
    with pytest.raises(ChunkValidationError, match="관절 수"):
        MOVENET_ADAPTER.validate_frame(Frame.model_validate({"t": 0, "landmarks": lms}))
    lms[0] = {"x": 0.5, "y": 0.1, "visibility": 0.9}
    with pytest.raises(ChunkValidationError, match="얼굴"):
        MEDIAPIPE_ADAPTER.validate_frame(Frame.model_validate({"t": 0, "landmarks": lms}))
    MEDIAPIPE_ADAPTER.validate_frame(Frame(t=0, landmarks=None))


def _frame_with(index_map: dict[Joint, int], n: int) -> Frame:
    lms: list[Landmark | None] = [None] * n
    for j, i in index_map.items():
        if j is Joint.NOSE:
            continue
        lms[i] = Landmark(x=0.01 * (j + 1), y=0.02 * (j + 1), visibility=0.5 + 0.03 * j)
    return Frame(t=5, landmarks=lms)


@pytest.mark.parametrize(
    ("adapter", "imap", "n"),
    [(MEDIAPIPE_ADAPTER, MEDIAPIPE_INDEX, 33), (MOVENET_ADAPTER, MOVENET_INDEX, 17)],
)
def test_mapping_to_pixels(adapter, imap, n) -> None:  # type: ignore[no-untyped-def]
    sk = adapter.to_skeleton(_frame_with(imap, n), 100, 200, mirrored=False)
    assert sk.joints is not None and len(sk.joints) == 13
    assert sk.joints[Joint.NOSE] is None
    p = sk.joints[Joint.LEFT_KNEE]
    assert p is not None
    assert p.x == pytest.approx(0.01 * (Joint.LEFT_KNEE + 1) * 100)
    assert p.y == pytest.approx(0.02 * (Joint.LEFT_KNEE + 1) * 200)


def test_mirrored_swaps_left_right_and_flips_x() -> None:
    fr = _frame_with(MEDIAPIPE_INDEX, 33)
    plain = MEDIAPIPE_ADAPTER.to_skeleton(fr, 100, 200, mirrored=False)
    mir = MEDIAPIPE_ADAPTER.to_skeleton(fr, 100, 200, mirrored=True)
    assert plain.joints is not None and mir.joints is not None
    a = plain.joints[Joint.LEFT_WRIST]
    b = mir.joints[Joint.RIGHT_WRIST]
    assert a is not None and b is not None
    assert b.y == a.y and b.x == pytest.approx(100 - a.x) and b.vis == a.vis


def test_null_frame() -> None:
    assert MOVENET_ADAPTER.to_skeleton(Frame(t=1, landmarks=None), 10, 10, False).joints is None
