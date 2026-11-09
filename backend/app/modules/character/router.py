"""character API. 노션 '전운시 API 명세서' API-006~008.

API-006 캐릭터 생성, API-007 내 캐릭터·성장 조회, API-008 캐릭터 수정.
에러 본문은 노션 명세 공통 규칙 { code, message, details } (errors.py).
"""

import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.character import service
from app.modules.character.deps import get_current_user_id
from app.modules.character.errors import ApiError, ApiErrorRoute
from app.modules.character.schemas import (
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
    ErrorResponse,
    ExpRead,
    MyCharacterRead,
)

router = APIRouter(tags=["character"], route_class=ApiErrorRoute)


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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    avatar_id = body.avatar_id if body is not None else None
    try:
        return service.create_character(db, user_id, avatar_id)
    except service.CharacterAlreadyExists:
        raise ApiError(409, "INVALID_STATE", "이미 캐릭터가 있습니다.")


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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        growth = service.get_my_character_growth(db, user_id)
    except service.CharacterNotFound:
        raise ApiError(404, "NOT_FOUND", "캐릭터가 아직 없습니다.")
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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(include=body.model_fields_set)
    try:
        return service.update_my_character(db, user_id, **changes)
    except service.CharacterNotFound:
        raise ApiError(404, "NOT_FOUND", "캐릭터가 아직 없습니다.")
