from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

_MAX_LIMIT = 200


class RecordSummary(BaseModel):
    """One row in the records list — just enough to render in a table."""

    model_config = ConfigDict(extra="forbid")

    id: int
    source_system: str
    source_id: str
    entity_type: str
    fetched_at: datetime


class RecordDetail(BaseModel):
    """One row drilled-down with full raw + normalized payloads."""

    model_config = ConfigDict(extra="forbid")

    id: int
    source_system: str
    source_id: str
    entity_type: str
    fetched_at: datetime
    payload_hash: str
    raw: dict[str, Any]
    normalized: dict[str, Any]


class RecordsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecordSummary]
    limit: int


def clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_LIMIT))
