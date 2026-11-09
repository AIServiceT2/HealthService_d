"""character API. 노션 '전운시 API 명세서' API-006~008.

API-006 캐릭터 생성, API-007 내 캐릭터·성장 조회, API-008 캐릭터 수정.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.character import service
from app.modules.character.schemas import (
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
    ErrorResponse,
    ExpRead,
    MyCharacterRead,
)

# 입력 오류는 전역 처리기가 422가 아니라 400 VALIDATION_FAILED로 돌려준다.
# FastAPI는 라우트에 422·4XX·default 응답이 없으면 Swagger에 422를 자동으로 넣으므로,
# 공통 에러 본문을 4XX로 선언해 실제와 다른 422가 문서에 보이지 않게 한다.
router = APIRouter(
    tags=["character"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)


def _not_found() -> AppError:
    return AppError(404, "NOT_FOUND", "캐릭터가 아직 없습니다.")


@router.post(
    "/characters",
    summary="[API-006] 캐릭터 생성",
    description="권한: PLAYER. 사용자당 캐릭터 1개. avatarId는 선택(선택 범위 미정).",
    status_code=201,
    response_model=CharacterRead,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 캐릭터가 있습니다."},
    },
)
def create_character(
    body: CharacterCreate | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    avatar_id = body.avatar_id if body is not None else None
    try:
        return service.create_character(db, user.id, avatar_id)
    except service.CharacterAlreadyExists:
        raise AppError(409, "INVALID_STATE", "이미 캐릭터가 있습니다.")


@router.get(
    "/characters/me",
    summary="[API-007] 내 캐릭터·성장 조회",
    description=(
        "권한: PLAYER. 본인 캐릭터만 조회. "
        "임시: level은 저장값(성장 공식 미정), exp.pending·lockedItemCount는 0(지급 내역·아이템 미구현), stats는 빈 배열(능력치 축 미정)."
    ),
    response_model=MyCharacterRead,
    response_model_by_alias=True,
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 캐릭터가 아직 없습니다."},
    },
)
def read_my_character(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        growth = service.get_my_character_growth(db, user.id)
    except service.CharacterNotFound:
        raise _not_found()
    return MyCharacterRead(
        user_id=growth.user_id,
        avatar_id=growth.avatar_id,
        level=growth.level,
        exp=ExpRead(confirmed=growth.exp_confirmed, pending=growth.exp_pending),
        stats=[],
        locked_item_count=growth.locked_item_count,
    )


@router.patch(
    "/characters/me",
    summary="[API-008] 캐릭터 수정",
    description=(
        "권한: PLAYER. 본인 캐릭터만 수정. 수정 가능한 필드는 미정이라 avatarId만 받는다. "
        "보내지 않은 필드는 그대로, null이면 아바타를 비움. 다른 필드(level·exp 등)를 보내면 400."
    ),
    response_model=CharacterRead,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 캐릭터가 아직 없습니다."},
    },
)
def update_my_character(
    body: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(include=body.model_fields_set)
    try:
        return service.update_my_character(db, user.id, **changes)
    except service.CharacterNotFound:
        raise _not_found()
