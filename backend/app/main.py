"""서버 진입점. 모듈형 모놀리스: 서버는 하나, 기능은 app/modules/<모듈>/로 나눈다.

모듈마다 router.py(API)·service.py(규칙)·schemas.py(입출력)·models.py(테이블)를 두고,
다른 모듈은 service를 통해서만 부른다 (docs/decisions/scaffold-log.md 1절).
"""

from fastapi import FastAPI

from app.core.errors import install_error_handlers
from app.modules.auth.router import router as auth_router
from app.modules.battle.router import router as battle_router
from app.modules.character.router import router as character_router
from app.modules.guild.router import router as guild_router
from app.modules.health.router import router as health_router
from app.modules.llm.router import router as llm_router
from app.modules.result.router import router as result_router
from app.modules.review.router import router as review_router
from app.modules.reward.router import router as reward_router
from app.modules.snapshot.router import router as snapshot_router
from app.modules.submission.router import router as submission_router
from app.modules.submission.router import stub_router as submission_stub_router
from app.modules.workout_session.router import router as workout_session_router

app = FastAPI(title="전운시 API")
install_error_handlers(app)  # 에러 본문 { code, message, details } (노션 API 명세서 공통 규칙)
app.include_router(health_router)
app.include_router(submission_router)

# 아래는 노션 'API 명세서' MVP 필수(API-001~051)의 빈 API. 기능 없이 501을 돌려준다.
app.include_router(auth_router)
app.include_router(character_router)
app.include_router(guild_router)
app.include_router(workout_session_router)
app.include_router(submission_stub_router)
app.include_router(snapshot_router)
app.include_router(review_router)
app.include_router(reward_router)
app.include_router(battle_router)
app.include_router(result_router)
app.include_router(llm_router)
