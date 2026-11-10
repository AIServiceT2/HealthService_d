"""스냅샷 API 입출력. JSON 키는 노션 API 명세서대로 camelCase."""

import uuid

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class SnapshotValues(_CamelModel):
    """스냅샷 수치: { catalogVersion, hitCount, exp, totalDamage, weaknessMultiplier, dropCount }."""

    catalog_version: str
    hit_count: int
    exp: int
    total_damage: int
    weakness_multiplier: float
    drop_count: int


class SnapshotRead(SnapshotValues):
    """API-031 응답 200: SnapshotValues + submissionId."""

    submission_id: uuid.UUID


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | list | None = None
