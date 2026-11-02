"""환경 변수에서 설정을 읽는다. 값은 .env(저장소에 올리지 않음)나 셸에서 넣는다."""

import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:5432/jeonunsi",
)
