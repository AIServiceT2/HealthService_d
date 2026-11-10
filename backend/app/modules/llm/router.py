"""llm API. 노션 '전운시 API 명세서' API-049~051. 모두 서버 내부 호출 전용(/internal).

LLM 제공사·모델은 미정이라 지금은 모의 응답(client.MockLLMClient)으로 동작한다.
/internal 확인은 snapshot 모듈의 require_internal_token(X-Internal-Token)을 같이 쓴다.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.stub import not_implemented
from app.modules.llm import service
from app.modules.llm.client import LLMClient, get_llm_client
from app.modules.llm.schemas import (
    ErrorResponse,
    FormCommentRequest,
    GeneratedText,
    NarrativeRequest,
)
from app.modules.snapshot.internal import require_internal_token

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["llm"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
    dependencies=[Depends(require_internal_token)],
)


def _errors(fn):
    try:
        return fn()
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.InvalidState:
        raise AppError(409, "INVALID_STATE", "글을 만들 수 없는 상태의 제출건입니다.")


def _rate_limited(result: service.Generated) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "code": "RATE_LIMITED",
            "message": "LLM 호출 한도를 넘었습니다.",
            "details": {"fallbackSaved": True, "level": result.level},
        },
    )


@router.post(
    "/internal/llm/narratives",
    summary="[API-049] L3 전투 서사 생성",
    description=(
        "권한: SYSTEM (X-Internal-Token). LLM에는 스킬명·운동 종류·적 이름·약점 적중 여부만 보낸다. "
        "숫자·다른 스킬명·아이템명이 있으면 다시 만들고 2번 실패하면 기본 문구(isFallback=true). ai_story에 저장. "
        "호출 한도 초과는 429(기본 문구는 저장). 제공사 미정이라 지금은 모의 응답"
    ),
    response_model=GeneratedText,
)
def api_049(
    req: NarrativeRequest,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
):
    try:
        result = _errors(lambda: service.generate_narrative(db, client, req.submission_id))
    except service.RateLimited as e:
        return _rate_limited(e.result)
    return GeneratedText(level=result.level, text=result.text, is_fallback=result.is_fallback)


@router.post(
    "/internal/llm/form-comments",
    summary="[API-050] L4 자세 교정 코멘트 생성",
    description=(
        "권한: SYSTEM (X-Internal-Token). 관절 좌표 원본 대신 각도 요약 통계(poseSummary, 0~180도, 관절 최대 10개)만 "
        "받아 운동 종류·판정 기준과 함께 보낸다(입력 계약 미정). 숫자나 진단·처방처럼 들리는 표현이 있으면 다시 만들고 "
        "2번 실패하면 기본 문구. ai_form_tip에 저장. 호출 한도 초과는 429. 제공사 미정이라 지금은 모의 응답"
    ),
    response_model=GeneratedText,
)
def api_050(
    req: FormCommentRequest,
    db: Session = Depends(get_db),
    client: LLMClient = Depends(get_llm_client),
):
    pose = {k: v.model_dump(exclude_none=True) for k, v in req.pose_summary.items()}
    try:
        result = _errors(lambda: service.generate_form_tip(db, client, req.submission_id, pose))
    except service.RateLimited as e:
        return _rate_limited(e.result)
    return GeneratedText(level=result.level, text=result.text, is_fallback=result.is_fallback)


@router.post(
    "/internal/llm/review-summaries",
    summary="[API-051] L1 기록 요약·L2 이상치 설명 생성",
    description="권한: SYSTEM",
    status_code=501,
)
def api_051() -> None:
    not_implemented()
