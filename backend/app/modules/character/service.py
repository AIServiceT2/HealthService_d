"""캐릭터 규칙. 다른 모듈은 이 파일의 함수로만 캐릭터를 다룬다."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.character.models import INITIAL_EXP, INITIAL_LEVEL, Character


class CharacterAlreadyExists(Exception):
    pass


class CharacterNotFound(Exception):
    pass


@dataclass(frozen=True)
class CharacterGrowth:
    """API-007 내 캐릭터·성장 조회 결과."""

    user_id: uuid.UUID
    avatar_id: str | None
    level: int
    exp_confirmed: int
    exp_pending: int
    locked_item_count: int


_UNSET = object()


def has_character(db: Session, user_id: uuid.UUID) -> bool:
    """사용자에게 캐릭터가 있는지 (노션 API-005 hasCharacter)."""
    return db.scalar(select(Character.id).where(Character.user_id == user_id)) is not None


def update_my_character(db: Session, user_id: uuid.UUID, avatar_id: object = _UNSET) -> Character:
    """본인 캐릭터만 수정한다 (노션 API-008). 없으면 CharacterNotFound.

    수정 가능한 필드는 미정이라 avatar_id만. 인자를 넘기지 않으면 바꾸지 않는다.
    """
    try:
        character = db.scalars(
            select(Character).where(Character.user_id == user_id).with_for_update()
        ).one_or_none()
        if character is None:
            raise CharacterNotFound(str(user_id))
        if avatar_id is not _UNSET:
            character.avatar_id = avatar_id
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(character)
    return character


def get_my_character_growth(db: Session, user_id: uuid.UUID) -> CharacterGrowth:
    """본인 캐릭터만 조회한다 (노션 API-007). 없으면 CharacterNotFound.

    - exp_pending: 지급 뒤 24시간 보호 기간 중인 경험치 (reward 모듈). character.exp에는 지급 때 이미 더해져
      있으므로 exp_confirmed = character.exp - exp_pending
    - locked_item_count: LOCKED 아이템 수 (reward 모듈)
    - level: 명세는 'exp로 계산한 값'이지만 성장 공식이 미정 (노션 기능명세 JN-010) → 저장된 level을 그대로 씀 (임시)
    """
    # reward 모듈이 character 모델을 쓰므로 순환 import를 피하려고 함수 안에서 가져온다
    from app.modules.reward import service as reward_service

    character = db.scalars(select(Character).where(Character.user_id == user_id)).one_or_none()
    if character is None:
        raise CharacterNotFound(str(user_id))
    pending = reward_service.pending_exp(db, user_id)

    return CharacterGrowth(
        user_id=character.user_id,
        avatar_id=character.avatar_id,
        level=character.level,
        exp_confirmed=character.exp - pending,
        exp_pending=pending,
        locked_item_count=reward_service.locked_item_count(db, user_id),
    )


def create_character(db: Session, user_id: uuid.UUID, avatar_id: str | None) -> Character:
    """사용자당 캐릭터 1개 (노션 API-006). 이미 있으면 CharacterAlreadyExists.

    동시에 두 요청이 와도 user_id 유니크 제약으로 하나만 저장된다.
    """
    existing = db.scalars(select(Character).where(Character.user_id == user_id)).one_or_none()
    if existing is not None:
        raise CharacterAlreadyExists(str(user_id))

    character = Character(
        user_id=user_id,
        avatar_id=avatar_id,
        level=INITIAL_LEVEL,
        exp=INITIAL_EXP,
    )
    db.add(character)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CharacterAlreadyExists(str(user_id))
    db.refresh(character)
    return character
