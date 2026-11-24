"""로그인한 사용자 확인 (Authorization: Bearer <access_token>).

다른 모듈도 권한이 PLAYER 이상인 API에서 Depends(get_current_user)로 쓴다.
"""

import uuid
from datetime import UTC, datetime

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import jwt_secret
from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.auth.service import JWT_ALGORITHM

# auto_error=False: 토큰이 없을 때도 FastAPI 기본 403 대신 명세의 401로 보낸다
_bearer = HTTPBearer(auto_error=False)


def _unauthenticated() -> AppError:
    return AppError(401, "UNAUTHENTICATED", "Bearer 토큰이 필요하거나 유효하지 않습니다.")


def read_access_token(token: str) -> tuple[uuid.UUID, datetime]:
    """access token을 검사해 (user_id, 만료 시각)을 돌려준다. 틀리거나 만료되면 401 AppError.

    헤더를 쓰지 않는 WebSocket(길드 채팅 API-075)도 같은 검사를 쓰려고 get_current_user에서 나눴다.
    """
    try:
        claims = jwt.decode(
            token,
            jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if claims.get("type") != "access":
            raise _unauthenticated()
        return uuid.UUID(claims["sub"]), datetime.fromtimestamp(claims["exp"], UTC)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise _unauthenticated() from None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthenticated()
    user_id, _ = read_access_token(credentials.credentials)

    user = db.get(User, user_id)
    if user is None:
        raise _unauthenticated()
    return user
