"""snapshot API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["snapshot"])


@router.post(
    "/internal/submissions/{id}/snapshot",
    summary="[API-031] 보상 스냅샷 계산·고정",
    description="권한: SYSTEM",
    status_code=501,
)
def api_031(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/submissions/{id}/reward-preview",
    summary="[API-032] 보상·타격 수 미리보기",
    description="권한: OWNER",
    status_code=501,
)
def api_032(id: uuid.UUID) -> None:
    not_implemented()
