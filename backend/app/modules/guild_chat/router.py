"""길드 채팅 API. 노션 '전운시 API 명세서' API-072~075 (2026-11-24 저장소에서 추가, 기능명세 JN-040).

구현: API-073 메시지 보내기.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.guild.schemas import ErrorResponse
from app.modules.guild_chat import service
from app.modules.guild_chat.schemas import MessageCreate, MessageRead, MessageSender

router = APIRouter(
    tags=["guild-chat"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_UNAUTHENTICATED = {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."}
_NOT_MEMBER = {"model": ErrorResponse, "description": "FORBIDDEN 길드 소속원만 이용할 수 있습니다."}
_NO_GUILD = {"model": ErrorResponse, "description": "NOT_FOUND 길드가 없습니다."}


def _read(view: service.MessageView) -> MessageRead:
    return MessageRead(
        message_id=view.message_id,
        type=view.type,
        sender=MessageSender(user_id=view.sender.user_id, nickname=view.sender.nickname) if view.sender else None,
        body=view.body,
        payload=view.payload,
        created_at=view.created_at,
        deleted=view.deleted,
    )


def _membership_errors(fn):
    """길드 없음 404, 소속원 아님 403 (노션 API-072~074 Error Code)."""
    try:
        return fn()
    except service.GuildNotFound:
        raise AppError(404, "NOT_FOUND", "길드가 없습니다.")
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 이용할 수 있습니다.")


@router.post(
    "/guilds/{guild_id}/chat/messages",
    summary="[API-073] 길드 채팅 메시지 보내기",
    description=(
        "권한: GUILD_MEMBER. body는 앞뒤 공백을 지운 뒤 1~300자 [제안]. 텍스트만 보낼 수 있다. "
        "같은 clientMessageId로 다시 보내면 새로 만들지 않고 처음 메시지를 200으로 돌려준다 (새로 저장하면 201). "
        "보내기 간격 제한(도배 방지)은 미정."
    ),
    status_code=201,
    response_model=MessageRead,
    response_model_by_alias=True,
    responses={
        200: {"model": MessageRead, "description": "같은 clientMessageId로 이미 저장된 메시지"},
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 메시지는 1~300자여야 합니다."},
        401: _UNAUTHENTICATED,
        403: _NOT_MEMBER,
        404: _NO_GUILD,
    },
)
def send_message(
    guild_id: uuid.UUID,
    body: MessageCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    view, created = _membership_errors(
        lambda: service.send_message(db, user.id, guild_id, body.client_message_id, body.body)
    )
    if not created:
        response.status_code = 200
    return _read(view)
