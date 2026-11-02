"""서버 진입점. 모듈형 모놀리스: 서버는 하나, 기능은 app/modules/<모듈>/로 나눈다.

모듈마다 router.py(API)·service.py(규칙)·schemas.py(입출력)·models.py(테이블)를 두고,
다른 모듈은 service를 통해서만 부른다 (docs/decisions/scaffold-log.md 1절).
"""

from fastapi import FastAPI

from app.modules.health.router import router as health_router
from app.modules.submission.router import router as submission_router

app = FastAPI(title="전운시 API")
app.include_router(health_router)
app.include_router(submission_router)
