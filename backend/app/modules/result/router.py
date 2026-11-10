"""result API. 노션 '전운시 API 명세서' API-047·048.

구현: API-047 결과 카드·서사·교정 코멘트 조회, API-048 전투 리플레이 조회.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.result import service
from app.modules.result.schemas import (
    CardRead,
    DropRead,
    ErrorResponse,
    ReplayEventRead,
    ReplayRead,
    ResultRead,
    TextRead,
)

# 입력 오류는 전역 처리기가 400으로 돌려주므로 Swagger에 실제와 다른 422가 보이지 않게 4XX를 선언한다
router = APIRouter(
    tags=["result"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_OWNER_ERRORS = {
    401: {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."},
    403: {"model": ErrorResponse, "description": "FORBIDDEN 본인만 볼 수 있습니다."},
    404: {"model": ErrorResponse, "description": "NOT_FOUND 제출건을 찾을 수 없습니다."},
    409: {"model": ErrorResponse, "description": "INVALID_STATE 아직 보상이 지급되지 않았습니다."},
}


def _owner_rewarded_errors(fn):
    try:
        return fn()
    except service.SubmissionNotFound:
        raise AppError(404, "NOT_FOUND", "제출건을 찾을 수 없습니다.")
    except service.NotOwner:
        raise AppError(403, "FORBIDDEN", "본인만 볼 수 있습니다.")
    except service.NotRewarded:
        raise AppError(409, "INVALID_STATE", "아직 보상이 지급되지 않았습니다.")


def _text(level: str, saved: str | None, fallback: str) -> TextRead:
    return TextRead(level=level, text=saved or fallback, is_fallback=saved is None)


@router.get(
    "/submissions/{id}/result",
    summary="[API-047] 결과 카드·서사·교정 코멘트 조회",
    description=(
        "권한: OWNER. REWARDED 건만, 상태는 바꾸지 않는다. 수치는 모두 스냅샷·지급 결과. "
        "card.dailyCapExceeded(명세에 없음, 추가): 타격 0이면 true → 리플레이 없이 '일일 상한 초과' 카드. "
        "서사(L3)·교정 코멘트(L4)는 LLM 연결 전이라 기본 문구와 isFallback=true (문구는 DESIGN.md 5절 제안)."
    ),
    response_model=ResultRead,
    response_model_by_alias=True,
    responses=_OWNER_ERRORS,
)
def read_result(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    card = _owner_rewarded_errors(lambda: service.get_card(db, user.id, id))
    submission = card.submission
    return ResultRead(
        card=CardRead(
            exercise_code=submission.exercise_code,
            counted_reps=submission.counted_reps,
            hit_count=card.snapshot.hit_count,
            exp=card.snapshot.exp,
            total_damage=card.snapshot.total_damage,
            drops=[DropRead(item_id=i.id, status=i.status) for i in card.drops],
            rewarded_at=card.rewarded_at,
            daily_cap_exceeded=card.daily_cap_exceeded,
        ),
        narrative=_text("L3", submission.ai_story, service.FALLBACK_NARRATIVE),
        form_comment=_text("L4", submission.ai_form_tip, service.FALLBACK_FORM_COMMENT),
    )


@router.get(
    "/submissions/{id}/replay",
    summary="[API-048] 전투 리플레이 조회",
    description=(
        "권한: OWNER. REWARDED 건만. HIT 수 = hitCount(결과 카드 타격 수), HIT 피해 합 = 결과 카드 totalDamage. "
        "t는 세션 시작부터의 초를 30초 안으로 줄인 재생 시각(제안). 상한을 넘은 인정 렙은 MISS(DAILY_CAP), "
        "미인정 렙은 MISS(사유 null, 저장되지 않음). 타격 0(일일 상한 초과)이면 409 reason DAILY_CAP_EXCEEDED. "
        "skeletonUrl은 자료 저장소가 없어 null. 길드원 공개 여부는 미정이라 본인만."
    ),
    response_model=ReplayRead,
    response_model_by_alias=True,
    responses=_OWNER_ERRORS
    | {
        409: {
            "model": ErrorResponse,
            "description": "INVALID_STATE 아직 보상이 지급되지 않았습니다. / 일일 상한 초과로 리플레이가 없습니다. (reason DAILY_CAP_EXCEEDED)",
        }
    },
)
def read_replay(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        replay = _owner_rewarded_errors(lambda: service.get_replay(db, user.id, id))
    except service.DailyCapExceeded:
        raise AppError(
            409, "INVALID_STATE", "일일 상한 초과로 리플레이가 없습니다.", {"reason": "DAILY_CAP_EXCEEDED"}
        )
    return ReplayRead(
        hit_count=replay.hit_count,
        events=[
            ReplayEventRead(rep_index=e.rep_index, t=e.t, type=e.type, damage=e.damage, reason=e.reason)
            for e in replay.events
        ],
        skeleton_url=None,
    )
