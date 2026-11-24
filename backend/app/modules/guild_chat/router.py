"""길드 채팅 API. 노션 '전운시 API 명세서' API-072~075 (2026-11-24 저장소에서 추가, 기능명세 JN-040).

구현: API-072 메시지 목록, API-073 메시지 보내기, API-074 메시지 삭제(숨김).
로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.guild.schemas import ErrorResponse
from app.modules.guild_chat import service
from app.modules.guild_chat.schemas import (
    MessageCreate,
    MessageDeleted,
    MessageList,
    MessageRead,
    MessageSender,
)

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


@router.get(
    "/guilds/{guild_id}/chat/messages",
    summary="[API-072] 길드 채팅 메시지 목록",
    description=(
        "권한: GUILD_MEMBER. items는 오래된 것 → 최근 순. 아무 값도 없으면 최근 limit개. "
        "cursor(앞 응답의 nextCursor)는 더 이전 메시지, after(messageId)는 그 메시지 뒤에 온 메시지 "
        "(재연결 뒤 빠진 메시지 채우기, nextCursor는 null). cursor와 after는 함께 쓸 수 없다. "
        "숨긴 메시지는 deleted: true이고 body·payload가 null. limit 기본 20, 최대 50."
    ),
    response_model=MessageList,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED cursor와 after는 함께 쓸 수 없습니다. (cursor 형식, after 메시지, limit 범위)"},
        401: _UNAUTHENTICATED,
        403: _NOT_MEMBER,
        404: _NO_GUILD,
    },
)
def list_messages(
    guild_id: uuid.UUID,
    cursor: str | None = Query(default=None, description="더 이전 메시지 페이지 커서 (앞 응답의 nextCursor)"),
    after: uuid.UUID | None = Query(default=None, description="이 messageId 뒤에 온 메시지만"),
    limit: int = Query(default=20, ge=1, le=50, description="기본 20, 최대 50"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if cursor is not None and after is not None:
        raise AppError(400, "VALIDATION_FAILED", "cursor와 after는 함께 쓸 수 없습니다.")
    try:
        page = _membership_errors(lambda: service.list_messages(db, user.id, guild_id, cursor, after, limit))
    except service.InvalidCursor:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"cursor": "형식이 올바르지 않습니다."})
    except service.AfterMessageNotFound:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"after": "이 길드의 메시지가 아닙니다."})
    return MessageList(
        items=[_read(v) for v in page.items],
        next_cursor=page.next_cursor,
        has_more_after=page.has_more_after,
    )


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


@router.delete(
    "/guilds/{guild_id}/chat/messages/{message_id}",
    summary="[API-074] 길드 채팅 메시지 삭제",
    description=(
        "권한: GUILD_MEMBER. 지우지 않고 숨긴다. 본인은 자기 TEXT만, 길드장은 그 길드의 모든 메시지(알림 포함)를 숨길 수 있다. "
        "이미 숨긴 메시지를 다시 요청하면 같은 결과를 돌려준다. deletedBy는 AUTHOR | LEADER "
        "(길드장이 자기 메시지를 숨기면 AUTHOR)."
    ),
    response_model=MessageDeleted,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 본인 메시지나 길드장만 삭제할 수 있습니다. (길드 소속원이 아니어도 403)"},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 메시지가 없습니다."},
    },
)
def delete_message(
    guild_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = service.delete_message(db, user.id, guild_id, message_id)
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 이용할 수 있습니다.")
    except service.CannotDelete:
        raise AppError(403, "FORBIDDEN", "본인 메시지나 길드장만 삭제할 수 있습니다.")
    except service.MessageNotFound:
        raise AppError(404, "NOT_FOUND", "메시지가 없습니다.")
    return MessageDeleted(message_id=result.message_id, deleted_by=result.deleted_by)
