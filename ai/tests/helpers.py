"""테스트용 작은 빌더 (합성 스쿼트는 synth.py)."""

from __future__ import annotations

from typing import Any

from rep_engine.landmarks import (
    MEDIAPIPE_FACE_INDICES,
    MEDIAPIPE_NUM_LANDMARKS,
    MOVENET_FACE_INDICES,
    MOVENET_NUM_LANDMARKS,
)


def raw_landmarks(family: str = "mediapipe", vis: float = 0.9) -> list[dict[str, Any] | None]:
    n, face = (
        (MEDIAPIPE_NUM_LANDMARKS, MEDIAPIPE_FACE_INDICES)
        if family == "mediapipe"
        else (MOVENET_NUM_LANDMARKS, MOVENET_FACE_INDICES)
    )
    out: list[dict[str, Any] | None] = []
    for i in range(n):
        if i in face:
            out.append(None)
        else:
            out.append(
                {"x": 0.5, "y": 0.5, "z": 0.0 if family == "mediapipe" else None, "visibility": vis}
            )
    return out


def meta_dict(model_version: str = "mediapipe-pose-full@0.10", **kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "sessionId": "s1",
        "exerciseType": "SQUAT",
        "catalogVersion": "cat_2026-11-01",
        "fps": 15,
        "imageWidth": 720,
        "imageHeight": 1280,
        "mirrored": False,
        "device": {"platform": "ANDROID", "modelVersion": model_version},
        "liveness": None,
    }
    d.update(kw)
    return d
