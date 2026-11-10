"""길드 규칙. 다른 모듈은 이 파일의 함수로만 길드를 다룬다."""

import base64
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.guild.models import (
    INVITE_CODE_ALPHABET,
    INVITE_CODE_LENGTH,
    Guild,
    GuildInvitation,
)


class AlreadyInGuild(Exception):
    pass


class GuildNotFound(Exception):
    pass


class NotGuildMember(Exception):
    pass


class InvalidCursor(Exception):
    pass


class NotGuildLeader(Exception):
    pass


class InvitationNotFound(Exception):
    pass


class InvitationExpired(Exception):
    pass


class LeaderCannotLeave(Exception):
    pass


class CannotTargetSelf(Exception):
    pass


class MemberNotFound(Exception):
    pass


class AlreadyLeader(Exception):
    pass


_INVITE_CODE_ATTEMPTS = 5


ROLE_LEADER = "LEADER"
ROLE_MEMBER = "MEMBER"


@dataclass(frozen=True)
class GuildMember:
    user_id: uuid.UUID
    nickname: str
    role: str


@dataclass(frozen=True)
class GuildMemberPage:
    """API-011 길드원 목록 한 쪽. next_cursor가 None이면 마지막 쪽."""

    items: list[GuildMember]
    next_cursor: str | None


@dataclass(frozen=True)
class GuildInfo:
    """API-010 길드 정보 조회 결과."""

    id: uuid.UUID
    name: str
    leader_user_id: uuid.UUID
    leader_nickname: str
    member_count: int


def _locked(stmt):
    """행 잠금 + 이미 읽어 둔 객체도 DB 값으로 다시 채움 (잠근 뒤 최신 값을 보장)."""
    return stmt.with_for_update().execution_options(populate_existing=True)


def _lock_user(db: Session, user_id: uuid.UUID) -> User:
    """사용자 행을 잠근다. 같은 사용자의 길드 요청이 동시에 와도 하나씩 처리된다.

    로그인 확인(get_current_user)이 같은 세션에서 User를 이미 읽어 두었으므로 populate_existing으로
    잠근 뒤 DB 값을 다시 채운다. 없으면 다른 요청이 커밋한 guild_id를 못 보고 예전 값을 쓴다.
    """
    return db.scalars(_locked(select(User).where(User.id == user_id))).one()


def _lock_guild(db: Session, guild_id: uuid.UUID) -> Guild | None:
    """길드 행을 잠근다. 탈퇴·내보내기·위임이 같은 길드에 동시에 와도 하나씩 처리된다.

    잠그는 순서는 항상 길드 → 사용자 (교착 상태를 피하려고).
    """
    return db.scalars(_locked(select(Guild).where(Guild.id == guild_id))).one_or_none()


def is_guild_leader(db: Session, user: User) -> bool:
    """사용자가 소속 길드의 길드장인가 (노션 API-005 isGuildLeader)."""
    if user.guild_id is None:
        return False
    leader = db.scalar(select(Guild.leader_user_id).where(Guild.id == user.guild_id))
    return leader == user.id


def create_guild(db: Session, user_id: uuid.UUID, name: str) -> Guild:
    """길드를 만들고 만든 사람을 길드장·소속원으로 둔다 (노션 API-009).

    이미 다른 길드에 소속되어 있으면 AlreadyInGuild.
    """
    try:
        user = _lock_user(db, user_id)
        if user.guild_id is not None:
            raise AlreadyInGuild(str(user_id))
        guild = Guild(name=name, leader_user_id=user_id)
        db.add(guild)
        db.flush()
        user.guild_id = guild.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return guild


def get_guild_info(db: Session, user_id: uuid.UUID, guild_id: uuid.UUID) -> GuildInfo:
    """길드 소속원만 조회한다 (노션 API-010).

    길드가 없으면 GuildNotFound, 있지만 요청한 사람이 소속원이 아니면 NotGuildMember.
    """
    guild = db.get(Guild, guild_id)
    if guild is None:
        raise GuildNotFound(str(guild_id))
    requester = db.get(User, user_id)
    if requester is None or requester.guild_id != guild.id:
        raise NotGuildMember(str(user_id))

    leader = db.get(User, guild.leader_user_id)
    member_count = db.scalar(select(func.count()).select_from(User).where(User.guild_id == guild.id))
    return GuildInfo(
        id=guild.id,
        name=guild.name,
        leader_user_id=leader.id,
        leader_nickname=leader.nickname,
        member_count=member_count,
    )


# 커서: 마지막 항목의 user_id를 base64url로 감싼 값.
# 클라이언트는 받은 값을 그대로 돌려보내기만 한다 (형식은 서버 내부 약속).
def _encode_cursor(user_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(str(user_id).encode()).decode()


def _decode_cursor(cursor: str) -> uuid.UUID:
    try:
        return uuid.UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
    except ValueError:
        raise InvalidCursor(cursor) from None


def list_guild_members(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, cursor: str | None, limit: int
) -> GuildMemberPage:
    """길드 소속원만 목록을 본다 (노션 API-011). user_id 순, 길드장은 role로 구분한다.

    정렬에 '길드장 먼저'를 넣으면 페이지를 넘기는 중에 위임이 일어날 때 순서가 바뀌어
    중복·누락이 생기므로, 바뀌지 않는 user_id로만 정렬한다.
    요청한 사람이 그 길드 소속원이 아니면 NotGuildMember (없는 길드도 같음 — 명세 에러는 403뿐).
    커서가 올바르지 않으면 InvalidCursor.
    """
    requester = db.get(User, user_id)
    if requester is None or requester.guild_id != guild_id:
        raise NotGuildMember(str(user_id))
    guild = db.get(Guild, guild_id)

    query = select(User.id, User.nickname).where(User.guild_id == guild_id)
    if cursor is not None:
        query = query.where(User.id > _decode_cursor(cursor))
    rows = db.execute(query.order_by(User.id).limit(limit + 1)).all()

    page, more = rows[:limit], len(rows) > limit
    items = [
        GuildMember(
            user_id=r.id,
            nickname=r.nickname,
            role=ROLE_LEADER if r.id == guild.leader_user_id else ROLE_MEMBER,
        )
        for r in page
    ]
    next_cursor = _encode_cursor(page[-1].id) if more else None
    return GuildMemberPage(items=items, next_cursor=next_cursor)


def _new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


def issue_invitation(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, expires_in_hours: int
) -> GuildInvitation:
    """그 길드의 길드장만 초대 코드를 발급한다 (노션 API-012).

    길드장이 아니면 NotGuildLeader (소속원이 아니거나 없는 길드도 같음 — 명세 에러는 403뿐).
    길드 행을 잠근 채 길드장인지 확인하므로, 위임과 동시에 와도 이전 길드장은 발급할 수 없다.
    코드가 이미 쓰인 값과 겹치면 새로 뽑아 다시 저장한다.
    """
    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=expires_in_hours)
    for _ in range(_INVITE_CODE_ATTEMPTS):
        guild = _lock_guild(db, guild_id)
        if guild is None or guild.leader_user_id != user_id:
            db.rollback()
            raise NotGuildLeader(str(user_id))
        invitation = GuildInvitation(
            code=_new_invite_code(), guild_id=guild_id, created_by=user_id, expires_at=expires_at
        )
        db.add(invitation)
        try:
            db.commit()
        except IntegrityError:
            # 코드 겹침. 롤백하면 잠금도 풀리므로 다음 시도에서 다시 잠그고 확인한다
            db.rollback()
            continue
        return invitation
    raise RuntimeError("초대 코드를 만들지 못했습니다 (겹침 반복).")


# 추천 길드 개수 (시안 'F-01 길드 가입'에 3개) [제안·팀 확인 필요]
RECOMMENDED_LIMIT = 3


@dataclass(frozen=True)
class RecommendedGuild:
    guild_id: uuid.UUID
    name: str
    member_count: int


def list_recommended_guilds(db: Session, limit: int = RECOMMENDED_LIMIT) -> list[RecommendedGuild]:
    """가입 화면의 추천 길드. 길드원이 많은 순, 같으면 이름·ID 순 [제안: 추천 기준 미정, 노션 명세에 없는 API]."""
    count = func.count(User.id)
    rows = db.execute(
        select(Guild.id, Guild.name, count)
        .join(User, User.guild_id == Guild.id, isouter=True)
        .group_by(Guild.id, Guild.name)
        .order_by(count.desc(), Guild.name, Guild.id)
        .limit(limit)
    ).all()
    return [RecommendedGuild(guild_id=r[0], name=r[1], member_count=r[2]) for r in rows]


def join_guild(db: Session, user_id: uuid.UUID, guild_id: uuid.UUID) -> uuid.UUID:
    """추천 길드에서 골라 초대 코드 없이 가입한다 [제안: 노션 명세에 없는 API].

    없는 길드면 GuildNotFound, 이미 길드에 소속되어 있으면 AlreadyInGuild.
    잠그는 순서는 길드 → 사용자 (탈퇴·내보내기와 같음).
    """
    try:
        guild = _lock_guild(db, guild_id)
        if guild is None:
            raise GuildNotFound(str(guild_id))
        user = _lock_user(db, user_id)
        if user.guild_id is not None:
            raise AlreadyInGuild(str(user_id))
        user.guild_id = guild.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return guild_id


def join_by_invitation(db: Session, user_id: uuid.UUID, code: str) -> uuid.UUID:
    """초대 코드로 길드에 가입하고 길드 ID를 돌려준다 (노션 API-013).

    없는 코드면 InvitationNotFound, 만료된 코드면 InvitationExpired,
    이미 길드에 소속되어 있으면 AlreadyInGuild. 같은 코드는 만료 전까지 여러 명이 쓸 수 있다.
    """
    try:
        user = _lock_user(db, user_id)
        invitation = db.get(GuildInvitation, code)
        if invitation is None:
            raise InvitationNotFound(code)
        if invitation.expires_at <= datetime.now(UTC):
            raise InvitationExpired(code)
        if user.guild_id is not None:
            raise AlreadyInGuild(str(user_id))
        user.guild_id = invitation.guild_id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invitation.guild_id


def leave_guild(db: Session, user_id: uuid.UUID, guild_id: uuid.UUID) -> None:
    """본인이 길드를 탈퇴한다 (노션 API-014). 탈퇴 제한 정책은 미정이라 명세의 규칙만 둔다.

    그 길드 소속원이 아니면 NotGuildMember, 길드장이면 LeaderCannotLeave(위임 후 탈퇴).
    """
    try:
        guild = _lock_guild(db, guild_id)
        user = _lock_user(db, user_id)
        if guild is None or user.guild_id != guild.id:
            raise NotGuildMember(str(user_id))
        if guild.leader_user_id == user.id:
            raise LeaderCannotLeave(str(user_id))
        user.guild_id = None
        db.commit()
    except Exception:
        db.rollback()
        raise


def kick_member(db: Session, leader_id: uuid.UUID, guild_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """길드장이 길드원을 내보낸다 (노션 API-015).

    요청한 사람이 그 길드의 길드장이 아니면 NotGuildLeader, 본인을 지정하면 CannotTargetSelf,
    대상이 그 길드원이 아니면 MemberNotFound.
    """
    try:
        guild = _lock_guild(db, guild_id)
        if guild is None or guild.leader_user_id != leader_id:
            raise NotGuildLeader(str(leader_id))
        if target_id == leader_id:
            raise CannotTargetSelf(str(target_id))
        target = db.scalars(_locked(select(User).where(User.id == target_id))).one_or_none()
        if target is None or target.guild_id != guild.id:
            raise MemberNotFound(str(target_id))
        target.guild_id = None
        db.commit()
    except Exception:
        db.rollback()
        raise


def delegate_leader(db: Session, leader_id: uuid.UUID, guild_id: uuid.UUID, target_id: uuid.UUID) -> Guild:
    """길드장을 같은 길드원에게 넘긴다 (노션 API-016). 위임 상세 정책은 미정.

    요청한 사람이 그 길드의 길드장이 아니면 NotGuildLeader, 본인을 지정하면 AlreadyLeader
    [제안·팀 확인 필요], 대상이 그 길드원이 아니면 MemberNotFound.
    이전 길드장은 일반 길드원으로 남는다.
    """
    try:
        guild = _lock_guild(db, guild_id)
        if guild is None or guild.leader_user_id != leader_id:
            raise NotGuildLeader(str(leader_id))
        if target_id == leader_id:
            raise AlreadyLeader(str(target_id))
        target = db.scalars(_locked(select(User).where(User.id == target_id))).one_or_none()
        if target is None or target.guild_id != guild.id:
            raise MemberNotFound(str(target_id))
        guild.leader_user_id = target.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    return guild
