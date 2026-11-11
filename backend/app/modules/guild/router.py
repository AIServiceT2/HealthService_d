"""guild API. 노션 '전운시 API 명세서' API-009~017.

구현: API-009~016 (길드 생성·정보 조회·길드원 목록·초대 코드 발급·가입·탈퇴·내보내기·길드장 위임).
API-017 지인 목록은 노션 가안(같은 길드원)으로 구현.
로그인 확인은 auth 모듈의 get_current_user (Bearer access token, JWT).
에러 본문 { code, message, details }은 전역 처리기(app/core/errors.py)가 만든다.
"""

import uuid

from fastapi import APIRouter, Body, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.guild import service
from app.modules.guild.schemas import (
    AcquaintanceList,
    AcquaintanceRead,
    ErrorResponse,
    GuildCreate,
    GuildCreated,
    GuildJoin,
    GuildJoined,
    GuildLeader,
    GuildMemberList,
    GuildMemberRead,
    GuildRead,
    InvitationCreate,
    InvitationCreated,
    LeaderDelegate,
    LeaderDelegated,
    RecommendedGuildList,
    RecommendedGuildRead,
)

# 입력 오류는 전역 처리기가 400 VALIDATION_FAILED로 돌려주므로, Swagger에 실제와 다른 422가
# 보이지 않게 공통 에러 본문을 4XX로 선언한다 (character 라우터와 같은 방식)
router = APIRouter(
    tags=["guild"],
    responses={"4XX": {"model": ErrorResponse, "description": "공통 에러 본문 { code, message, details }"}},
)

_UNAUTHENTICATED = {"model": ErrorResponse, "description": "UNAUTHENTICATED 로그인이 필요합니다."}


@router.post(
    "/guilds",
    summary="[API-009] 길드 생성",
    description="권한: PLAYER. name은 2~20자(앞뒤 공백 제외). 만든 사람이 길드장이 된다.",
    status_code=201,
    response_model=GuildCreated,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 다른 길드에 소속되어 있습니다."},
    },
)
def create_guild(
    body: GuildCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        guild = service.create_guild(db, user.id, body.name)
    except service.AlreadyInGuild:
        raise AppError(409, "INVALID_STATE", "이미 다른 길드에 소속되어 있습니다.")
    return GuildCreated(guild_id=guild.id, name=guild.name, leader_user_id=guild.leader_user_id)


# /guilds/{guild_id}보다 먼저 둔다 ('recommended'가 guild_id로 읽히지 않게)
@router.get(
    "/guilds/recommended",
    summary="[추가] 추천 길드 목록",
    description=(
        "권한: PLAYER. 노션 명세에 없는 API (시안 'F-01 길드 가입'의 추천 길드, 2026-11-11 팀 요청). "
        "길드원이 많은 순으로 최대 3개 [제안: 추천 기준 미정]. 길드장 닉네임은 보내지 않는다."
    ),
    response_model=RecommendedGuildList,
    response_model_by_alias=True,
    responses={401: _UNAUTHENTICATED},
)
def recommended_guilds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    guilds = service.list_recommended_guilds(db)
    return RecommendedGuildList(
        items=[RecommendedGuildRead(guild_id=g.guild_id, name=g.name, member_count=g.member_count) for g in guilds]
    )


@router.post(
    "/guilds/{guild_id}/members/me",
    summary="[추가] 추천 길드에 가입",
    description=(
        "권한: PLAYER. 노션 명세에 없는 API (추천 길드를 골라 초대 코드 없이 가입, 2026-11-11 팀 요청). "
        "응답은 API-013과 같은 { guildId }."
    ),
    response_model=GuildJoined,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        404: {"model": ErrorResponse, "description": "NOT_FOUND 길드를 찾을 수 없습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 길드에 소속되어 있습니다."},
    },
)
def join_recommended_guild(
    guild_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        joined = service.join_guild(db, user.id, guild_id)
    except service.GuildNotFound:
        raise AppError(404, "NOT_FOUND", "길드를 찾을 수 없습니다.")
    except service.AlreadyInGuild:
        raise AppError(409, "INVALID_STATE", "이미 길드에 소속되어 있습니다.")
    return GuildJoined(guild_id=joined)


@router.get(
    "/guilds/{guild_id}",
    summary="[API-010] 길드 정보 조회",
    description="권한: GUILD_MEMBER. 그 길드 소속원만 조회할 수 있다.",
    response_model=GuildRead,
    response_model_by_alias=True,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드 소속원만 조회할 수 있습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 길드를 찾을 수 없습니다."},
    },
)
def read_guild(
    guild_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        info = service.get_guild_info(db, user.id, guild_id)
    except service.GuildNotFound:
        raise AppError(404, "NOT_FOUND", "길드를 찾을 수 없습니다.")
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 조회할 수 있습니다.")
    return GuildRead(
        id=info.id,
        name=info.name,
        leader=GuildLeader(user_id=info.leader_user_id, nickname=info.leader_nickname),
        member_count=info.member_count,
    )


@router.get(
    "/guilds/{guild_id}/members",
    summary="[API-011] 길드원 목록",
    description=(
        "권한: GUILD_MEMBER. userId 순으로 정렬하고 길드장은 role=LEADER로 구분한다. "
        "cursor는 앞 응답의 nextCursor를 그대로 넣는다. limit 기본 20, 최대 50."
    ),
    response_model=GuildMemberList,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다. (limit 범위, cursor 형식)"},
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드 소속원만 조회할 수 있습니다."},
    },
)
def list_guild_members(
    guild_id: uuid.UUID,
    cursor: str | None = Query(default=None, description="다음 페이지 커서 (앞 응답의 nextCursor)"),
    limit: int = Query(default=20, ge=1, le=50, description="기본 20, 최대 50"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        page = service.list_guild_members(db, user.id, guild_id, cursor, limit)
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 조회할 수 있습니다.")
    except service.InvalidCursor:
        raise AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"cursor": "형식이 올바르지 않습니다."})
    return GuildMemberList(
        items=[GuildMemberRead(user_id=m.user_id, nickname=m.nickname, role=m.role) for m in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "/guilds/{guild_id}/invitations",
    summary="[API-012] 길드 초대 코드 발급",
    description=(
        "권한: GUILD_LEADER. 본문은 선택. expiresInHours 기본 72, 1~168 (명세는 기본값 미정 — 제안·팀 확인 필요). "
        "초대 코드는 영문 대문자·숫자 6자."
    ),
    status_code=201,
    response_model=InvitationCreated,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드장만 초대 코드를 발급할 수 있습니다."},
    },
)
def issue_invitation(
    guild_id: uuid.UUID,
    body: InvitationCreate | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hours = (body or InvitationCreate()).expires_in_hours
    try:
        invitation = service.issue_invitation(db, user.id, guild_id, hours)
    except service.NotGuildLeader:
        raise AppError(403, "FORBIDDEN", "길드장만 초대 코드를 발급할 수 있습니다.")
    return InvitationCreated(invite_code=invitation.code, expires_at=invitation.expires_at)


@router.post(
    "/guilds/join",
    summary="[API-013] 초대 코드로 길드 가입",
    description=(
        "권한: PLAYER. inviteCode는 영문·숫자 6자 (소문자도 대문자로 바꿔 받음). "
        "같은 코드는 만료 전까지 여러 명이 쓸 수 있다."
    ),
    response_model=GuildJoined,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 초대 코드 형식이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        404: {"model": ErrorResponse, "description": "NOT_FOUND 초대 코드를 찾을 수 없습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 만료된 코드이거나 이미 길드에 소속되어 있습니다."},
    },
)
def join_guild(
    body: GuildJoin,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        guild_id = service.join_by_invitation(db, user.id, body.invite_code)
    except service.InvitationNotFound:
        raise AppError(404, "NOT_FOUND", "초대 코드를 찾을 수 없습니다.")
    except service.InvitationExpired:
        raise AppError(409, "INVALID_STATE", "만료된 초대 코드입니다.")
    except service.AlreadyInGuild:
        raise AppError(409, "INVALID_STATE", "이미 길드에 소속되어 있습니다.")
    return GuildJoined(guild_id=guild_id)


@router.delete(
    "/guilds/{guild_id}/members/me",
    summary="[API-014] 길드 탈퇴",
    description=(
        "권한: GUILD_MEMBER. 본문 없음, 성공 시 204. 길드장은 위임(API-016) 후 탈퇴할 수 있다. "
        "탈퇴 제한 정책은 미정."
    ),
    status_code=204,
    response_class=Response,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드 소속원만 탈퇴할 수 있습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 길드장은 위임 후 탈퇴할 수 있습니다."},
    },
)
def leave_guild(
    guild_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.leave_guild(db, user.id, guild_id)
    except service.NotGuildMember:
        raise AppError(403, "FORBIDDEN", "길드 소속원만 탈퇴할 수 있습니다.")
    except service.LeaderCannotLeave:
        raise AppError(409, "INVALID_STATE", "길드장은 위임 후 탈퇴할 수 있습니다.")
    return Response(status_code=204)


@router.delete(
    "/guilds/{guild_id}/members/{user_id}",
    summary="[API-015] 길드원 내보내기",
    description="권한: GUILD_LEADER. 본문 없음, 성공 시 204. 길드장 본인은 지정할 수 없다.",
    status_code=204,
    response_class=Response,
    responses={
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드장만 내보낼 수 있으며 본인은 지정할 수 없습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 해당 길드원을 찾을 수 없습니다."},
    },
)
def kick_member(
    guild_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.kick_member(db, user.id, guild_id, user_id)
    except service.NotGuildLeader:
        raise AppError(403, "FORBIDDEN", "길드장만 내보낼 수 있습니다.")
    except service.CannotTargetSelf:
        raise AppError(403, "FORBIDDEN", "본인은 내보낼 수 없습니다.")
    except service.MemberNotFound:
        raise AppError(404, "NOT_FOUND", "해당 길드원을 찾을 수 없습니다.")
    return Response(status_code=204)


@router.post(
    "/guilds/{guild_id}/leader",
    summary="[API-016] 길드장 위임",
    description=(
        "권한: GUILD_LEADER. 새 길드장은 같은 길드원이어야 한다. 이전 길드장은 일반 길드원으로 남는다. "
        "본인을 지정하면 409 (명세에 없음 — 제안·팀 확인 필요). 위임 상세 정책은 미정."
    ),
    response_model=LeaderDelegated,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse, "description": "VALIDATION_FAILED 입력값이 올바르지 않습니다."},
        401: _UNAUTHENTICATED,
        403: {"model": ErrorResponse, "description": "FORBIDDEN 길드장만 위임할 수 있습니다."},
        404: {"model": ErrorResponse, "description": "NOT_FOUND 해당 길드원을 찾을 수 없습니다."},
        409: {"model": ErrorResponse, "description": "INVALID_STATE 이미 길드장입니다."},
    },
)
def delegate_leader(
    guild_id: uuid.UUID,
    body: LeaderDelegate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        guild = service.delegate_leader(db, user.id, guild_id, body.user_id)
    except service.NotGuildLeader:
        raise AppError(403, "FORBIDDEN", "길드장만 위임할 수 있습니다.")
    except service.AlreadyLeader:
        raise AppError(409, "INVALID_STATE", "이미 길드장입니다.")
    except service.MemberNotFound:
        raise AppError(404, "NOT_FOUND", "해당 길드원을 찾을 수 없습니다.")
    return LeaderDelegated(guild_id=guild.id, leader_user_id=guild.leader_user_id)


@router.get(
    "/me/acquaintances",
    summary="[API-017] 확인 요청 가능한 지인 목록",
    description=(
        "권한: PLAYER. 지인 = 같은 길드원(본인 제외), 노션 명세 가안. 길드장 먼저. 길드가 없으면 빈 목록. "
        "확인 요청(API-035)은 이 목록에 있는 사람에게만 보낼 수 있다. '지인' 정의는 미정 [가안·팀 확인 필요]."
    ),
    response_model=AcquaintanceList,
    response_model_by_alias=True,
    responses={401: _UNAUTHENTICATED},
)
def list_acquaintances(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = service.list_acquaintances(db, user.id)
    return AcquaintanceList(
        items=[AcquaintanceRead(user_id=a.user_id, nickname=a.nickname, relation=a.relation) for a in items]
    )
