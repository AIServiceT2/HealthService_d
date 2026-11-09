"""로그인한 사용자 확인 (Authorization: Bearer <access_token>).

다른 모듈도 권한이 PLAYER 이상인 API에서 Depends(get_current_user)로 쓴다.
"""

import uuid

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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthenticated()
    try:
        claims = jwt.decode(
            credentials.credentials,
            jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if claims.get("type") != "access":
            raise _unauthenticated()
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthenticated() from None

    user = db.get(User, user_id)
    if user is None:
        raise _unauthenticated()
    return user
