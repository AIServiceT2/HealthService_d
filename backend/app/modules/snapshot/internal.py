"""서버 내부 호출(/internal/...) 확인. 노션 API 명세서 공통 규칙: '/internal은 서버 내부 호출 전용'.

X-Internal-Token 헤더가 환경 변수 INTERNAL_API_TOKEN과 같아야 한다. 환경 변수가 비어 있으면
모두 401 (ai/ 서비스의 AI_INTERNAL_TOKEN과 같은 방식). 값은 .env에만 두고 저장소에 넣지 않는다.
[제안] 다른 /internal API(review·reward·llm)도 쓰게 되면 app/core로 옮긴다 (공유 파일이라 테크리더 확인).
"""

import os
import secrets

from fastapi import Header

from app.core.errors import AppError

INTERNAL_TOKEN_ENV = "INTERNAL_API_TOKEN"


def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get(INTERNAL_TOKEN_ENV)
    if (
        not expected
        or x_internal_token is None
        or not secrets.compare_digest(x_internal_token.encode(), expected.encode())
    ):
        raise AppError(401, "UNAUTHENTICATED", "서버 내부 호출 전용입니다.")
