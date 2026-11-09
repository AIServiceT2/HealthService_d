"""전운시 AI 내부 API (SPEC 9.4). 백엔드 서버만 호출한다 (`http://ai:8001/internal/...`).

인증: `X-Internal-Token` 헤더를 환경변수 `AI_INTERNAL_TOKEN`과 비교한다.
환경변수가 비어 있으면 보호된 엔드포인트는 모두 401이다 (fail closed).

오류 형식: `{ "code", "message", "details" }`
- 400 `VALIDATION_FAILED`: 요청 형식·청크·모델·카탈로그 오류 (`details.missingSeq` 포함 가능)
- 400 `INVALID_REDUCTION`: 사용자가 서버 인정량보다 큰 값으로 '줄이기' 요청
- 401 `UNAUTHORIZED`
- 500 `CONFIG_ERROR`: 서버의 카탈로그 파일이 잘못됨
`SERVER_RECOUNT_MISMATCH`는 오류가 아니라 200 응답의 `comparison.errorCode`로 준다.
"""

from __future__ import annotations

import logging
import os
import secrets
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import Field

from rep_engine import ENGINE_VERSION
from rep_engine.adapters import adapter_for_model_version
from rep_engine.config import Catalog, list_catalog_versions, load_catalog
from rep_engine.errors import ChunkValidationError, EngineError
from rep_engine.liveness import evaluate_liveness, issue_challenge
from rep_engine.recount import compare, decide_approval
from rep_engine.schemas import (
    ApiModel,
    ApprovalDecision,
    Chunk,
    ClientSubmission,
    Frame,
    IssuedChallenge,
    LivenessResult,
    RecountComparison,
    SessionMeta,
    SessionResult,
)
from rep_engine.session import run_session
from rep_engine.validation import validate_time_order

TOKEN_ENV = "AI_INTERNAL_TOKEN"

logger = logging.getLogger("ai.service")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# --- 요청·응답 모델 ------------------------------------------------------------


class RecountRequest(ApiModel):
    meta: SessionMeta
    chunks: list[Chunk]
    client: ClientSubmission
    user_reduced_count: int | None = Field(default=None, ge=0)


class RecountResponse(ApiModel):
    result: SessionResult
    comparison: RecountComparison
    decision: ApprovalDecision


class LivenessEvaluateRequest(ApiModel):
    meta: SessionMeta
    frames: list[Frame]


class HealthResponse(ApiModel):
    status: str
    engine_version: str
    catalog_versions: list[str]


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any]


# --- 공통 ---------------------------------------------------------------------

_catalogs: dict[str, Catalog] = {}


def get_catalog(version: str) -> Catalog:
    """카탈로그를 한 번만 읽어 둔다 (파일은 배포 단위로만 바뀜)."""
    if version not in _catalogs:
        _catalogs[version] = load_catalog(version)
    return _catalogs[version]


def _error(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ErrorBody(code=code, message=message, details=details or {})
    return JSONResponse(status_code=status, content=body.to_dict())


class UnauthorizedError(Exception):
    pass


def require_token(x_internal_token: str | None = Header(default=None)) -> None:
    """`X-Internal-Token` 검사 (상수 시간 비교)."""
    expected = os.environ.get(TOKEN_ENV, "")
    if not expected or x_internal_token is None:
        raise UnauthorizedError
    if not secrets.compare_digest(x_internal_token.encode(), expected.encode()):
        raise UnauthorizedError


app = FastAPI(title="전운시 AI 내부 API", version=ENGINE_VERSION)


@app.middleware("http")
async def log_timing(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """요청마다 처리 시간(ms)을 표준 출력 로그로 남긴다."""
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "%s %s -> %d (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


@app.exception_handler(UnauthorizedError)
async def _unauthorized(_: Request, __: Exception) -> JSONResponse:
    return _error(401, "UNAUTHORIZED", "내부 토큰이 없거나 맞지 않음")


@app.exception_handler(RequestValidationError)
async def _invalid_request(_: Request, exc: Exception) -> JSONResponse:
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    slim = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in errors]
    return _error(400, "VALIDATION_FAILED", "요청 형식이 맞지 않음", {"errors": slim})


@app.exception_handler(EngineError)
async def _engine_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, EngineError):  # pragma: no cover  (등록한 타입만 들어옴)
        raise exc
    status = 500 if exc.code == "CONFIG_ERROR" else 400
    return _error(status, exc.code, exc.message, exc.details)


# --- 엔드포인트 -------------------------------------------------------------------


@app.get("/internal/health")
def health() -> dict[str, Any]:
    """상태 확인 (토큰 불필요)."""
    return HealthResponse(
        status="ok", engine_version=ENGINE_VERSION, catalog_versions=list_catalog_versions()
    ).to_dict()


@app.post("/internal/recount", dependencies=[Depends(require_token)])
def recount(req: RecountRequest) -> dict[str, Any]:
    """서버 재계산 + 클라이언트 비교 + 자동 승인 판정."""
    catalog = get_catalog(req.meta.catalog_version)
    result = run_session(req.meta, req.chunks, catalog)
    cfg = catalog.for_model(_family(req.meta))
    comparison = compare(result, req.client, cfg.recount, req.user_reduced_count)
    decision = decide_approval(result, comparison, cfg)
    return RecountResponse(result=result, comparison=comparison, decision=decision).to_dict()


@app.post("/internal/liveness/evaluate", dependencies=[Depends(require_token)])
def liveness_evaluate(req: LivenessEvaluateRequest) -> dict[str, Any]:
    """무작위 동작 구간 프레임만으로 판정한다. `meta.liveness`가 있어야 한다."""
    meta = req.meta
    if meta.liveness is None:
        raise ChunkValidationError("meta.liveness가 없음", {"field": "meta.liveness"})
    adapter = adapter_for_model_version(meta.device.model_version)
    for fr in req.frames:
        adapter.validate_frame(fr)
    validate_time_order(req.frames)
    cfg = get_catalog(meta.catalog_version).for_model(adapter.family)
    skeletons = (
        adapter.to_skeleton(f, meta.image_width, meta.image_height, meta.mirrored)
        for f in req.frames
    )
    res: LivenessResult = evaluate_liveness(
        meta.liveness, skeletons, cfg.liveness, cfg.features.min_visibility
    )
    return res.to_dict()


@app.post("/internal/liveness/issue", dependencies=[Depends(require_token)])
def liveness_issue() -> dict[str, Any]:
    """무작위 동작 1개 발급 (시각 issuedAtT·expiresAtT는 백엔드가 세션 기준으로 정함)."""
    issued: IssuedChallenge = issue_challenge()
    return issued.to_dict()


def _family(meta: SessionMeta) -> str:
    return adapter_for_model_version(meta.device.model_version).family
