"""Core event models for streamll.

This module defines the event schema that flows through the entire system.
Based on research of OpenTelemetry, LlamaIndex, and AWS Bedrock patterns.
Unified schema handles all event types: operations, tokens, errors.
"""

from datetime import UTC, datetime
from typing import Any

from nanoid import generate
from pydantic import AwareDatetime, BaseModel, Field


def generate_event_id() -> str:
    """Generate a unique event ID."""
    return generate(size=12)


class StreamllEvent(BaseModel):
    """Unified event model for all streamll events.

    Every event flowing through streamll conforms to this schema.
    Designed to be:
    - Self-contained (can be understood without other events)
    - Semantic (operation field provides domain meaning)
    - Extensible (data field allows arbitrary payloads)
    - Simple (minimal required fields, complex tracing via OTel later)
    """

    # Identity & ordering
    event_id: str = Field(default_factory=lambda: generate(size=12))
    execution_id: str = Field(description="Groups events from same forward() call")
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    # Source context
    module_name: str = Field(default="unknown", description="DSPy module or user-defined")
    method_name: str = Field(default="forward", description="Method being executed")

    # Event semantics
    event_type: str = Field(description="start, end, token, error")
    operation: str | None = Field(
        default=None, description="retrieval, ocr, chain_of_thought, etc."
    )

    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")

    # Optional metadata
    tags: dict[str, str] = Field(default_factory=dict, description="User-defined labels")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }
