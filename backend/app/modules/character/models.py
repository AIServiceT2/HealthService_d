"""캐릭터 (Character).

필드는 DATA-MODEL.md Character(★ user_id·level·exp)와 노션 API 명세서 API-006 응답을 따른다.
avatar_id는 노션 명세에만 있고 DATA-MODEL.md에는 없음 → 팀 확인 필요.
users 테이블이 아직 없어 user_id에 FK를 걸지 않는다 (auth 모듈 구현 후 추가).
"""

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

INITIAL_LEVEL = 1
INITIAL_EXP = 0


class Character(Base):
    __tablename__ = "character"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 사용자 1명당 1개 (DATA-MODEL.md, 노션 API-006)
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    # 선택 범위 미정 (노션 API-006)
    avatar_id: Mapped[str | None] = mapped_column(String(32), default=None)
    level: Mapped[int] = mapped_column(Integer, default=INITIAL_LEVEL)
    exp: Mapped[int] = mapped_column(Integer, default=INITIAL_EXP)
