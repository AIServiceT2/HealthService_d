"""현재 사용자 확인 — **임시**.

노션 API 명세서 공통 규칙: 공개 API 외에는 `Authorization: Bearer <access_token>`.
로그인(API-002)은 팀원이 구현 예정이라 토큰 검증 방법이 아직 없다.
그때까지 **토큰 값 자체를 사용자 UUID로 본다** (Swagger Authorize에 UUID를 넣어 테스트).
auth 모듈이 생기면 이 함수 하나만 실제 토큰 검증으로 바꾼다.
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.character.errors import ApiError

_bearer = HTTPBearer(auto_error=False, description="임시: access token 자리에 사용자 UUID를 넣는다")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    try:
        return uuid.UUID(credentials.credentials)
    except ValueError:
        raise ApiError(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
