"""노션 API 명세서 공통 에러 본문 { code, message, details }을 character 라우터에서만 쓴다.

API.md는 오류 형식이 아직 '미정'이고 다른 모듈은 FastAPI 기본 형식({"detail"})을 쓴다.
공유 파일(main.py)을 고치지 않으려고 이 라우터에만 적용하는 route_class를 둔다.
형식이 팀에서 확정되면 app/core로 옮겨 전역 처리기로 바꾼다 (테크리더).
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _error_response(status_code: int, code: str, message: str, details: dict | None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details},
    )


class ApiErrorRoute(APIRoute):
    """ApiError → 해당 status, 입력 검증 실패 → 400 VALIDATION_FAILED (노션 명세)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except ApiError as e:
                return _error_response(e.status_code, e.code, e.message, e.details)
            except RequestValidationError as e:
                return _error_response(
                    400,
                    "VALIDATION_FAILED",
                    "입력값이 올바르지 않습니다.",
                    {"errors": jsonable_encoder(e.errors())},
                )

        return wrapped
