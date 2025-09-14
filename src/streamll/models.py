from datetime import UTC, datetime
from typing import Any

from nanoid import generate
from pydantic import AwareDatetime, BaseModel, Field


def generate_event_id() -> str:
    return generate(size=12)


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: generate(size=12))
    execution_id: str
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    module_name: str = Field(default="unknown")
    method_name: str = Field(default="forward")

    event_type: str
    operation: str | None = None

    data: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }
