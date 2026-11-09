"""환경 변수에서 설정을 읽는다. 값은 .env(저장소에 올리지 않음)나 셸에서 넣는다."""

import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:5432/jeonunsi",
)

# 토큰 수명: 노션 API-002 가안 (access 30분, refresh 14일)
ACCESS_TOKEN_TTL_SECONDS = 30 * 60
REFRESH_TOKEN_TTL_SECONDS = 14 * 24 * 60 * 60


def jwt_secret() -> str:
    """access 토큰 서명 키. 기본값을 두지 않는다 — 없으면 토큰을 만들거나 검사할 때 실패한다."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET 환경 변수가 없습니다")
    return secret
