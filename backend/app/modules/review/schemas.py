"""review API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorResponse(_CamelModel):
    """공통 에러 본문 (app/core/errors.py). Swagger 표시용."""

    code: str
    message: str
    details: Any = None


# ---- API-033 자동 승인 판정 ----


class AutoApprovalResponse(_CamelModel):
    decision: str  # AUTO_APPROVED | NEEDS_REVIEW
    confidence: float
    threshold: float
    liveness_passed: bool | None
    submission_status: str
    approval_path: str | None


# ---- API-034 확인 요청 공유 내용 미리보기 ----


class Anomaly(_CamelModel):
    type: str
    rep_nos: list[int]
    description: str


class SharePreviewResponse(_CamelModel):
    # 영상·얼굴 없는 관절 선 리플레이. 만드는 기능이 아직 없어 null
    skeleton_replay_url: str | None
    # L1 기록 요약. LLM 연결 전이라 null (제출건 ai_summary)
    summary: str | None
    # L2 이상치 설명. LLM 연결 전이라 빈 배열
    anomalies: list[Anomaly]
    # 통증 안내 고정 문구는 미정 (노션 API-034)이라 null
    pain_notice: str | None
