"""제출건 API. 경로는 API.md에서 '미정' — 아래 경로는 제안이며 개발자2와 합의 필요."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
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
