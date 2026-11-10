"""session API. 노션 '전운시 API 명세서' API-018~027.

구현한 것: API-018~025. API-027(세션 폐기)은 아직 501.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token).
"""

import uuid

from fastapi import APIRouter, Depends

from app.core.stub import not_implemented
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workout_session.catalog import CATALOG_VERSION, EXERCISES
from app.modules.workout_session.schemas import (
    ExerciseCriteria,
    ExerciseItem,
    ExercisesResponse,
)

router = APIRouter(tags=["session"])


@router.get(
    "/exercises",
    summary="[API-018] 운동 목록·판정 기준·튜토리얼",
    description="권한: PLAYER. MVP 운동은 스쿼트 1종. 가동범위 수치·권장 촬영 각도·튜토리얼은 미정이라 null",
    response_model=ExercisesResponse,
)
def api_018(_: User = Depends(get_current_user)) -> ExercisesResponse:
    return ExercisesResponse(
        catalog_version=CATALOG_VERSION,
        items=[
            ExerciseItem(
                code=e.code, name=e.name, daily_cap=e.daily_cap, criteria=ExerciseCriteria()
            )
            for e in EXERCISES.values()
        ],
    )


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
