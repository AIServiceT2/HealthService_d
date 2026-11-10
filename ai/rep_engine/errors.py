"""엔진 예외 클래스."""

from __future__ import annotations


class EngineError(Exception):
    """엔진의 모든 예외의 부모."""

    code: str = "ENGINE_ERROR"

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = details or {}


class ChunkValidationError(EngineError):
    """업로드 좌표(메타·청크·프레임) 검증 실패. API에서는 VALIDATION_FAILED(400)."""

    code = "VALIDATION_FAILED"


class MissingChunksError(ChunkValidationError):
    """seq가 0..N-1로 이어지지 않을 때."""

    def __init__(self, missing_seq: list[int]) -> None:
        super().__init__(f"누락된 청크가 있음: {missing_seq}", {"missingSeq": list(missing_seq)})
        self.missing_seq = list(missing_seq)


class UnknownModelError(ChunkValidationError):
    """device.modelVersion에 맞는 어댑터가 없을 때."""


class UnsupportedExerciseError(ChunkValidationError):
    """요청한 catalogVersion에 meta.exerciseType의 판정 기준이 없을 때 (요청 문제라 400)."""


class ConfigError(EngineError):
    """카탈로그 설정 파일 누락·검증 실패."""

    code = "CONFIG_ERROR"


class CatalogNotFoundError(ConfigError):
    """catalogVersion에 해당하는 설정 파일이 없을 때. API에서는 VALIDATION_FAILED."""

    code = "VALIDATION_FAILED"


class InvalidReductionError(EngineError):
    """R12: 사용자가 횟수를 서버 인정량보다 크게 '줄이려' 할 때 (= 늘리기 요청)."""

    code = "INVALID_REDUCTION"
