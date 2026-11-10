"""길드 규칙. 다른 모듈은 이 파일의 함수로만 길드를 다룬다."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.guild.models import Guild


class AlreadyInGuild(Exception):
    pass


class GuildNotFound(Exception):
    pass


class NotGuildMember(Exception):
    pass


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
