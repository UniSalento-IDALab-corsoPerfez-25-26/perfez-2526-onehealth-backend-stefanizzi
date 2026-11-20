from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: UUID = Field(
        default_factory=uuid4
    )

    event_type: str

    event_version: str = "1.0"

    occurred_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    producer: str

    correlation_id: UUID = Field(
        default_factory=uuid4
    )

    causation_id: UUID | None = None

    dataset_version: str | None = None

    trace_id: str | None = None

    data: dict[str, Any]