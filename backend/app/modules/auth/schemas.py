"""auth 입출력. JSON 필드는 노션 명세대로 camelCase, 파이썬 이름은 snake_case."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# email-validator 패키지 없이 기본 형식만 검사한다
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SignupRequest(CamelModel):
    provider: Literal["EMAIL"]
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=2, max_length=12)
    birth_date: date


class SignupResponse(CamelModel):
    user_id: uuid.UUID
