"""길드 규칙. 다른 모듈은 이 파일의 함수로만 길드를 다룬다."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.guild.models import Guild


class AlreadyInGuild(Exception):
    pass


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
