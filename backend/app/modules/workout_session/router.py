"""session API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["session"])


@router.get(
    "/exercises",
    summary="[API-018] 운동 목록·판정 기준·튜토리얼",
    description="권한: PLAYER",
    status_code=501,
)
def api_018() -> None:
    not_implemented()


@router.get(
    "/me/daily-caps",
    summary="[API-019] 내 일일 상한 조회",
    description="권한: PLAYER",
    status_code=501,
)
def api_019() -> None:
    not_implemented()


@router.post(
    "/workout-sessions",
    summary="[API-020] 운동 세션 시작",
    description="권한: PLAYER",
    status_code=501,
)
def api_020() -> None:
    not_implemented()


@router.post(
    "/workout-sessions/{id}/liveness",
    summary="[API-021] 무작위 동작 확인 결과 전송",
    description="권한: OWNER",
    status_code=501,
)
def api_021(id: uuid.UUID) -> None:
    not_implemented()


@router.put(
    "/workout-sessions/{id}/pose-chunks/{seq}",
    summary="[API-022] 관절 좌표 청크 업로드",
    description="권한: OWNER",
    status_code=501,
)
def api_022(id: uuid.UUID, seq: int) -> None:
    not_implemented()


@router.post(
    "/workout-sessions/{id}/pause",
    summary="[API-023] 세션 일시중지",
    description="권한: OWNER",
    status_code=501,
)
def api_023(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/workout-sessions/{id}/resume",
    summary="[API-024] 세션 재개",
    description="권한: OWNER",
    status_code=501,
)
def api_024(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/workout-sessions/{id}",
    summary="[API-025] 세션 상태 조회",
    description="권한: OWNER",
    status_code=501,
)
def api_025(id: uuid.UUID) -> None:
    not_implemented()


@router.delete(
    "/workout-sessions/{id}",
    summary="[API-027] 세션 폐기",
    description="권한: OWNER",
    status_code=501,
)
def api_027(id: uuid.UUID) -> None:
    not_implemented()
