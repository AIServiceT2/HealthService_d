"""자세 추정 모델 출력 → 공통 골격(13개) 어댑터.

- `device.modelVersion`의 접두어로 어댑터를 고른다 (`mediapipe-pose…` / `movenet…`).
- 정규화 좌표를 픽셀 좌표로 바꾼다 (종횡비 보정). 이후 모든 각도·거리는 픽셀 단위.
- visibility(MediaPipe)와 score(MoveNet)는 둘 다 0~1로 받아 `vis`로 통일한다.
  두 값의 분포 차이는 카탈로그 `model_overrides.<family>.features.min_visibility`로 맞춘다.
- `mirrored=True`면 x를 1−x로 되돌리고 좌우 관절을 스왑한다 (미러링 해제).
- z는 쓰지 않는다 (MoveNet에는 z가 없음).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rep_engine.errors import ChunkValidationError, UnknownModelError
from rep_engine.landmarks import (
    MEDIAPIPE_FACE_INDICES,
    MEDIAPIPE_INDEX,
    MEDIAPIPE_NUM_LANDMARKS,
    MIRROR_OF,
    MOVENET_FACE_INDICES,
    MOVENET_INDEX,
    MOVENET_NUM_LANDMARKS,
    NUM_JOINTS,
    Joint,
)
from rep_engine.schemas import Frame


@dataclass(frozen=True, slots=True)
class Point:
    """공통 골격의 관절 1개. 픽셀 좌표(y 아래로 증가)와 0~1 가시도."""

    x: float
    y: float
    vis: float


@dataclass(frozen=True, slots=True)
class SkeletonFrame:
    """공통 골격 프레임. `joints`는 길이 13(`Joint` 순서), None = 사람 미검출.

    관절 하나가 None이면 그 관절은 없음(예: 서버로 받지 않는 코).
    """

    t: int
    joints: tuple[Point | None, ...] | None


@dataclass(frozen=True)
class PoseAdapter:
    """모델 1계열의 어댑터."""

    family: str
    num_landmarks: int
    index_map: dict[Joint, int]
    face_indices: frozenset[int]
    _table: tuple[tuple[int, int, int], ...] = field(init=False, repr=False, compare=False)

    def validate_frame(self, frame: Frame) -> None:
        """관절 수와 얼굴 인덱스 null 여부를 검사한다."""
        lms = frame.landmarks
        if lms is None:
            return
        if len(lms) != self.num_landmarks:
            raise ChunkValidationError(
                f"t={frame.t}: {self.family} 관절 수는 {self.num_landmarks}개여야 함 "
                f"({len(lms)}개)",
                {"t": frame.t},
            )
        for idx in self.face_indices:
            if lms[idx] is not None:
                raise ChunkValidationError(
                    f"t={frame.t}: 얼굴 랜드마크({idx})는 업로드하면 안 됨 (null이어야 함)",
                    {"t": frame.t, "index": idx},
                )

    def __post_init__(self) -> None:
        # (원본, 공통 골격, 미러링 시 공통 골격) 인덱스. 프레임마다 Enum을 다루지 않게 미리 만든다
        table = tuple(
            (src, int(joint), int(MIRROR_OF[joint])) for joint, src in self.index_map.items()
        )
        object.__setattr__(self, "_table", table)

    def to_skeleton(
        self, frame: Frame, image_width: int, image_height: int, mirrored: bool
    ) -> SkeletonFrame:
        """모델 원본 프레임 → 공통 골격(픽셀 좌표)."""
        lms = frame.landmarks
        if lms is None:
            return SkeletonFrame(frame.t, None)
        joints: list[Point | None] = [None] * NUM_JOINTS
        for src, plain, swapped in self._table:
            lm = lms[src]
            if lm is None:
                continue
            x_norm = 1.0 - lm.x if mirrored else lm.x
            vis = min(1.0, max(0.0, lm.visibility))
            joints[swapped if mirrored else plain] = Point(
                x_norm * image_width, lm.y * image_height, vis
            )
        return SkeletonFrame(frame.t, tuple(joints))


MEDIAPIPE_ADAPTER = PoseAdapter(
    "mediapipe", MEDIAPIPE_NUM_LANDMARKS, MEDIAPIPE_INDEX, MEDIAPIPE_FACE_INDICES
)
MOVENET_ADAPTER = PoseAdapter("movenet", MOVENET_NUM_LANDMARKS, MOVENET_INDEX, MOVENET_FACE_INDICES)

#: modelVersion 접두어 → 어댑터. 새 모델은 여기에 추가한다.
_PREFIXES: tuple[tuple[str, PoseAdapter], ...] = (
    ("mediapipe-pose", MEDIAPIPE_ADAPTER),
    ("movenet", MOVENET_ADAPTER),
)


def adapter_for_model_version(model_version: str) -> PoseAdapter:
    """`device.modelVersion`으로 어댑터를 고른다. 모르는 모델이면 `UnknownModelError`."""
    key = model_version.strip().lower()
    for prefix, adapter in _PREFIXES:
        if key == prefix or key.startswith(prefix + "-") or key.startswith(prefix + "@"):
            return adapter
    raise UnknownModelError(
        f"알 수 없는 자세 모델: {model_version}", {"modelVersion": model_version}
    )
