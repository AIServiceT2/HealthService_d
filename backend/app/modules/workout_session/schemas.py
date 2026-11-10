"""session API 입출력. JSON 키는 노션 API 명세서대로 camelCase, 파이썬 안에서는 snake_case."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- API-018 운동 목록 ----


class ExerciseCriteria(_CamelModel):
    # 가동범위 수치는 미정이라 null (노션 API-018). 엔진 가안 값은 ai/config/catalog에 있음
    knee_angle_max: float | None = None


class ExerciseItem(_CamelModel):
    code: str
    name: str
    daily_cap: int
    criteria: ExerciseCriteria
    recommended_camera_angle: str | None = None  # 권장 촬영 각도 미정 (PRD 미정 표)
    tutorial_url: str | None = None  # 튜토리얼 자료 없음


class ExercisesResponse(_CamelModel):
    catalog_version: str
    items: list[ExerciseItem]
