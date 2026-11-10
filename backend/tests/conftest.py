"""테스트는 실제 PostgreSQL(Docker Compose)로 돌린다 (STACK.md: SQLite로 대신하지 않음).

테스트는 매번 테이블을 비우므로 개발 DB가 아니라 테스트 전용 DB(docker-compose의 db-test, 55432)를 쓴다.
다른 DB를 쓰려면 TEST_DATABASE_URL을 넣는다. 셸의 DATABASE_URL(개발 DB)은 테스트에서 쓰지 않는다.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:55432/jeonunsi_test"
)

# 테스트 전용 서명 키 (실제 키가 아님). 셸에 JWT_SECRET이 있으면 그 값을 쓴다
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-not-for-production")

import pytest  # noqa: E402
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _tables():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE workout_submission, workout_session, pose_chunk, character, "
                "guild_invitation, guild, app_user, refresh_token CASCADE"
            )
        )


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)
