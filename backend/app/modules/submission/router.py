"""제출건 API. 경로는 API.md에서 '미정' — 아래 경로는 제안이며 개발자2와 합의 필요."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.stub import not_implemented
from app.modules.submission import service
from app.modules.submission.schemas import SubmissionRead

router = APIRouter(prefix="/submissions", tags=["submission"])


@router.get("/{submission_id}", response_model=SubmissionRead)
def read_submission(submission_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return service.get_submission(db, submission_id)
    except service.SubmissionNotFound:
        raise HTTPException(status_code=404, detail="submission not found")


@router.post("/{submission_id}/prepare", response_model=SubmissionRead)
def prepare_submission(submission_id: uuid.UUID, db: Session = Depends(get_db)):
    """보상 계산. 원래는 시스템이 실행하지만 오늘은 수동 호출로 대신한다 (API.md 항목 1 ①).

    오류 본문 형식은 API.md에서 미정이라 FastAPI 기본 형식({"detail": ...})을 쓴다.
    """
    try:
        return service.prepare_submission(db, submission_id)
    except service.SubmissionNotFound:
        raise HTTPException(status_code=404, detail="submission not found")
    except service.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    except service.CalculationError as e:
        raise HTTPException(status_code=500, detail=f"calculation failed: {e}")


# ---- 빈 API (노션 API 명세서, 기능 없음 → 501) ----
# 경로가 /submissions로 시작하지 않는 것도 있어 prefix 없는 라우터를 따로 둔다.
stub_router = APIRouter(tags=["submission"])


@stub_router.post(
    "/workout-sessions/{id}/submit",
    summary="[API-026] 세션 종료·운동 제출",
    description="권한: OWNER",
    status_code=501,
)
def api_026(id: uuid.UUID) -> None:
    not_implemented()


@stub_router.get(
    "/me/submissions",
    summary="[API-029] 내 제출 목록",
    description="권한: PLAYER",
    status_code=501,
)
def api_029() -> None:
    not_implemented()


@stub_router.post(
    "/submissions/{id}/cancel",
    summary="[API-030] 승인 전 제출 취소",
    description="권한: OWNER",
    status_code=501,
)
def api_030(id: uuid.UUID) -> None:
    not_implemented()
