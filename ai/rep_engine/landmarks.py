"""모델 독립 공통 골격(13개 관절)과 모델별 인덱스 매핑.

엔진 내부는 `Joint`만 쓴다. MediaPipe(33개)·MoveNet(COCO 17개)의 인덱스는
이 파일의 매핑과 `adapters.py`에서만 쓴다.

좌우(left/right)는 **사용자 본인 신체 기준**이다 (DECISIONS.md D-03).
"""

from __future__ import annotations

from enum import IntEnum


class Joint(IntEnum):
    """공통 골격 관절 번호 (0~12)."""

    NOSE = 0
    LEFT_SHOULDER = 1
    RIGHT_SHOULDER = 2
    LEFT_ELBOW = 3
    RIGHT_ELBOW = 4
    LEFT_WRIST = 5
    RIGHT_WRIST = 6
    LEFT_HIP = 7
    RIGHT_HIP = 8
    LEFT_KNEE = 9
    RIGHT_KNEE = 10
    LEFT_ANKLE = 11
    RIGHT_ANKLE = 12


NUM_JOINTS = len(Joint)

#: 좌우 스왑 대상 (미러링 해제·좌우 반전용). 코는 자기 자신.
MIRROR_OF: dict[Joint, Joint] = {
    Joint.NOSE: Joint.NOSE,
    Joint.LEFT_SHOULDER: Joint.RIGHT_SHOULDER,
    Joint.RIGHT_SHOULDER: Joint.LEFT_SHOULDER,
    Joint.LEFT_ELBOW: Joint.RIGHT_ELBOW,
    Joint.RIGHT_ELBOW: Joint.LEFT_ELBOW,
    Joint.LEFT_WRIST: Joint.RIGHT_WRIST,
    Joint.RIGHT_WRIST: Joint.LEFT_WRIST,
    Joint.LEFT_HIP: Joint.RIGHT_HIP,
    Joint.RIGHT_HIP: Joint.LEFT_HIP,
    Joint.LEFT_KNEE: Joint.RIGHT_KNEE,
    Joint.RIGHT_KNEE: Joint.LEFT_KNEE,
    Joint.LEFT_ANKLE: Joint.RIGHT_ANKLE,
    Joint.RIGHT_ANKLE: Joint.LEFT_ANKLE,
}

#: 한쪽 다리의 핵심 관절 (엉덩이, 무릎, 발목)
LEFT_LEG: tuple[Joint, Joint, Joint] = (Joint.LEFT_HIP, Joint.LEFT_KNEE, Joint.LEFT_ANKLE)
RIGHT_LEG: tuple[Joint, Joint, Joint] = (Joint.RIGHT_HIP, Joint.RIGHT_KNEE, Joint.RIGHT_ANKLE)

# --- MediaPipe Pose Landmarker (33개) ---------------------------------------
MEDIAPIPE_NUM_LANDMARKS = 33
MEDIAPIPE_INDEX: dict[Joint, int] = {
    Joint.NOSE: 0,
    Joint.LEFT_SHOULDER: 11,
    Joint.RIGHT_SHOULDER: 12,
    Joint.LEFT_ELBOW: 13,
    Joint.RIGHT_ELBOW: 14,
    Joint.LEFT_WRIST: 15,
    Joint.RIGHT_WRIST: 16,
    Joint.LEFT_HIP: 23,
    Joint.RIGHT_HIP: 24,
    Joint.LEFT_KNEE: 25,
    Joint.RIGHT_KNEE: 26,
    Joint.LEFT_ANKLE: 27,
    Joint.RIGHT_ANKLE: 28,
}
#: 얼굴 랜드마크(코·눈·귀·입). 서버로 보내지 않는다 (STACK.md, backlog US-01).
MEDIAPIPE_FACE_INDICES: frozenset[int] = frozenset(range(0, 11))

# --- MoveNet (COCO 17개) ----------------------------------------------------
MOVENET_NUM_LANDMARKS = 17
MOVENET_INDEX: dict[Joint, int] = {
    Joint.NOSE: 0,
    Joint.LEFT_SHOULDER: 5,
    Joint.RIGHT_SHOULDER: 6,
    Joint.LEFT_ELBOW: 7,
    Joint.RIGHT_ELBOW: 8,
    Joint.LEFT_WRIST: 9,
    Joint.RIGHT_WRIST: 10,
    Joint.LEFT_HIP: 11,
    Joint.RIGHT_HIP: 12,
    Joint.LEFT_KNEE: 13,
    Joint.RIGHT_KNEE: 14,
    Joint.LEFT_ANKLE: 15,
    Joint.RIGHT_ANKLE: 16,
}
#: 얼굴 키포인트(코·눈·귀). 서버로 보내지 않는다 (STACK.md).
MOVENET_FACE_INDICES: frozenset[int] = frozenset(range(0, 5))
