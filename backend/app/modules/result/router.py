"""result API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

import uuid

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["result"])


@router.get(
    "/submissions/{id}/result",
    summary="[API-047] 결과 카드·서사·교정 코멘트 조회",
    description="권한: OWNER",
    status_code=501,
)
def api_047(id: uuid.UUID) -> None:
    not_implemented()


@router.get(
    "/submissions/{id}/replay",
    summary="[API-048] 전투 리플레이 조회",
    description="권한: OWNER",
    status_code=501,
)
def api_048(id: uuid.UUID) -> None:
    not_implemented()
