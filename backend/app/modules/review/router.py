"""review API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["review"])


@router.post(
    "/internal/submissions/{id}/auto-approval",
    summary="[API-033] 자동 승인 판정",
    description="권한: SYSTEM",
    status_code=501,
)
def api_033(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/submissions/{id}/review-share-preview",
    summary="[API-034] 확인 요청 공유 내용 미리보기",
    description="권한: OWNER",
    status_code=501,
)
def api_034(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/submissions/{id}/review-requests",
    summary="[API-035] 지인·길드장에게 확인 요청",
    description="권한: OWNER",
    status_code=501,
)
def api_035(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/me/review-requests",
    summary="[API-036] 받은 확인 요청 목록",
    description="권한: REVIEWER",
    status_code=501,
)
def api_036() -> None:
    not_implemented()


@router.get(
    "/review-requests/{id}",
    summary="[API-037] 확인 자료 열람",
    description="권한: REVIEWER",
    status_code=501,
)
def api_037(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/review-requests/{id}/approve",
    summary="[API-038] 확인자 승인",
    description="권한: REVIEWER",
    status_code=501,
)
def api_038(id: uuid.UUID) -> None:
    not_implemented()


@router.post(
    "/review-requests/{id}/reject",
    summary="[API-039] 확인자 반려",
    description="권한: REVIEWER",
    status_code=501,
)
def api_039(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/reject-reasons",
    summary="[API-040] 반려 사유 코드 목록",
    description="권한: NONE",
    status_code=501,
)
def api_040() -> None:
    not_implemented()
