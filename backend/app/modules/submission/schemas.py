"""화면과 주고받는 형식. 필드 이름은 DATA-MODEL.md와 같다."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    exercise_type: str
    counted_reps: int
    snapshot: dict[str, Any] | None
