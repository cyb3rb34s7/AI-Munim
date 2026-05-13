"""Request and response Pydantic models for /api/connectors/*.

Per docs/conventions.md §4: every endpoint returns SuccessEnvelope[T]. The
T types live here; the envelope wrapper is applied in the router.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from munim.shared.constants import ConnectorName, CredentialStatus


class EntityCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    count: int


class ConnectorView(BaseModel):
    """One connector's state as the frontend sees it."""

    model_config = ConfigDict(extra="forbid")

    name: ConnectorName
    status: CredentialStatus | None  # None = not yet connected
    last_sync_at: datetime | None
    record_counts: list[EntityCount]


class ConnectorListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connectors: list[ConnectorView]


class ConnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: ConnectorView


class SyncResponse(BaseModel):
    """Mirrors munim.connectors.base.SyncResult, but flat for the JSON wire."""

    model_config = ConfigDict(extra="forbid")

    rows_upserted: int
    rows_skipped: int
    started_at: datetime
    finished_at: datetime
    connector: ConnectorView
