"""전투 API 입출력. JSON 키는 노션 API 명세서대로 camelCase."""

import uuid

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EnemyRead(_CamelModel):
    name: str
    hp_max: int
    hp: int


class DungeonProgressRead(_CamelModel):
    total_damage: int


class DungeonRead(_CamelModel):
    """API-045 응답 200: { id, name, enemy: { name, hpMax, hp }, myProgress: { totalDamage } }."""

    id: uuid.UUID
    name: str
    enemy: EnemyRead
    my_progress: DungeonProgressRead


class ErrorResponse(BaseModel):
    """노션 API 명세서 공통 에러 본문: { code, message, details }."""

    code: str
    message: str
    details: dict | list | None = None
