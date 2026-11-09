"""아직 기능이 없는 API가 공통으로 쓰는 501 응답."""

from fastapi import HTTPException


def not_implemented() -> None:
    raise HTTPException(status_code=501, detail="not implemented")
