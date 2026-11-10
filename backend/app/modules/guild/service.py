"""길드 규칙. 다른 모듈은 이 파일의 함수로만 길드를 다룬다."""

import base64
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select, tuple_
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


def _lock_user(db: Session, user_id: uuid.UUID) -> User:
    """사용자 행을 잠근다. 같은 사용자의 길드 요청이 동시에 와도 하나씩 처리된다."""
    return db.scalars(select(User).where(User.id == user_id).with_for_update()).one()


def _lock_guild(db: Session, guild_id: uuid.UUID) -> Guild | None:
    """길드 행을 잠근다. 탈퇴·내보내기·위임이 같은 길드에 동시에 와도 하나씩 처리된다.

    잠그는 순서는 항상 길드 → 사용자 (교착 상태를 피하려고).
    """
    return db.scalars(select(Guild).where(Guild.id == guild_id).with_for_update()).one_or_none()


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


# 커서: 마지막 항목의 정렬 키(길드장 0 / 길드원 1, user_id)를 base64url로 감싼 값.
# 클라이언트는 받은 값을 그대로 돌려보내기만 한다 (형식은 서버 내부 약속).
def _encode_cursor(rank: int, user_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{rank}:{user_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[int, uuid.UUID]:
    try:
        rank_text, user_text = base64.urlsafe_b64decode(cursor.encode()).decode().split(":")
        rank = int(rank_text)
        if rank not in (0, 1):
            raise ValueError(rank)
        return rank, uuid.UUID(user_text)
    except ValueError:
        raise InvalidCursor(cursor) from None


def list_guild_members(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, cursor: str | None, limit: int
) -> GuildMemberPage:
    """길드 소속원만 목록을 본다 (노션 API-011). 길드장이 맨 앞, 나머지는 user_id 순.

    요청한 사람이 그 길드 소속원이 아니면 NotGuildMember (없는 길드도 같음 — 명세 에러는 403뿐).
    커서가 올바르지 않으면 InvalidCursor.
    """
    requester = db.get(User, user_id)
    if requester is None or requester.guild_id != guild_id:
        raise NotGuildMember(str(user_id))
    guild = db.get(Guild, guild_id)

    rank = case((User.id == guild.leader_user_id, 0), else_=1)
    query = select(User.id, User.nickname, rank.label("rank")).where(User.guild_id == guild_id)
    if cursor is not None:
        after_rank, after_id = _decode_cursor(cursor)
        query = query.where(tuple_(rank, User.id) > tuple_(after_rank, after_id))
    rows = db.execute(query.order_by(rank, User.id).limit(limit + 1)).all()

    page, more = rows[:limit], len(rows) > limit
    items = [
        GuildMember(user_id=r.id, nickname=r.nickname, role=ROLE_LEADER if r.rank == 0 else ROLE_MEMBER)
        for r in page
    ]
    next_cursor = _encode_cursor(page[-1].rank, page[-1].id) if more else None
    return GuildMemberPage(items=items, next_cursor=next_cursor)


def _new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


def issue_invitation(
    db: Session, user_id: uuid.UUID, guild_id: uuid.UUID, expires_in_hours: int
) -> GuildInvitation:
    """그 길드의 길드장만 초대 코드를 발급한다 (노션 API-012).

    길드장이 아니면 NotGuildLeader (소속원이 아니거나 없는 길드도 같음 — 명세 에러는 403뿐).
    코드가 이미 쓰인 값과 겹치면 새로 뽑아 다시 저장한다.
    """
    guild = db.get(Guild, guild_id)
    if guild is None or guild.leader_user_id != user_id:
        raise NotGuildLeader(str(user_id))

    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=expires_in_hours)
    for _ in range(_INVITE_CODE_ATTEMPTS):
        invitation = GuildInvitation(
            code=_new_invite_code(), guild_id=guild_id, created_by=user_id, expires_at=expires_at
        )
        db.add(invitation)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return invitation
    raise RuntimeError("초대 코드를 만들지 못했습니다 (겹침 반복).")


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
        target = db.scalars(select(User).where(User.id == target_id).with_for_update()).one_or_none()
        if target is None or target.guild_id != guild.id:
            raise MemberNotFound(str(target_id))
        target.guild_id = None
        db.commit()
    except Exception:
        db.rollback()
        raise
