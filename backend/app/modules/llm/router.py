"""llm API. 노션 '전운시 API 명세서'의 MVP 필수 항목을 경로만 만든 것.

기능은 아직 없고 모두 501을 돌려준다. 입출력 형식은 명세 확정 후 schemas.py에 추가한다.
"""

from fastapi import APIRouter

from app.core.stub import not_implemented

router = APIRouter(tags=["llm"])


@router.post(
    "/internal/llm/narratives",
    summary="[API-049] L3 전투 서사 생성",
    description="권한: SYSTEM",
    status_code=501,
)
def api_049() -> None:
    not_implemented()


@router.post(
    "/internal/llm/form-comments",
    summary="[API-050] L4 자세 교정 코멘트 생성",
    description="권한: SYSTEM",
    status_code=501,
)
def api_050() -> None:
    not_implemented()


@router.post(
    "/internal/llm/review-summaries",
    summary="[API-051] L1 기록 요약·L2 이상치 설명 생성",
    description="권한: SYSTEM",
    status_code=501,
)
def api_051() -> None:
    not_implemented()
