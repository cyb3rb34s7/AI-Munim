"""Connector abstractions used by every source-specific connector.

The contract per docs/architecture.md §3.1:
  - One `BaseConnector` ABC; one method per lifecycle phase.
  - All connectors write rows ONLY through a `RowSink` (Task 5), so provenance
    stamping and natural-key upsert happen in one place.
  - `SyncContext` is the bag of dependencies a connector needs for one run;
    it is constructed by the caller (Phase 3: a FastAPI endpoint;
    Phase 2: a pytest test).

`Credential.blob` is opaque to the abstraction. In demo mode it carries
`{"status": "demo", "fixture_path": "<absolute path to fixture JSON>"}`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel

from munim.shared.constants import ConnectorName


class Credential(BaseModel):
    """Opaque credential bag passed from the credential store into a connector.

    The connector decides how to interpret `blob`. Demo mode uses:
        {"status": "demo", "fixture_path": "<absolute path>"}.
    """

    merchant_id: str
    connector: ConnectorName
    blob: dict[str, Any]


class SyncResult(BaseModel):
    rows_upserted: int = 0
    rows_skipped: int = 0
    started_at: datetime
    finished_at: datetime
    errors: list[str] = []


@dataclass
class SyncContext:
    """Bag of dependencies for one sync run.

    `row_sink` is the ONLY way the connector writes to the `record` table.
    `http_client` is provided by the caller so it can be mocked / pooled.
    """

    merchant_id: str
    credential: Credential
    row_sink: "RowSink"  # type: ignore[name-defined]  # noqa: F821  -- defined in _row_sink.py (Task 5)
    http_client: httpx.AsyncClient
    cursor: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """Every source-specific connector implements this contract."""

    name: ClassVar[ConnectorName]

    @abstractmethod
    def authorize_url(self, merchant_id: str) -> str:
        """OAuth URL the user is redirected to. Phase 3 wires the real flow."""

    @abstractmethod
    async def exchange_code(self, merchant_id: str, code: str) -> Credential:
        """Trade an OAuth code for a Credential. Phase 3."""

    @abstractmethod
    async def validate(self, credential: Credential) -> bool:
        """Quick credential health check."""

    @abstractmethod
    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        """Full backfill from the source."""

    async def sync_incremental(self, ctx: SyncContext) -> SyncResult:
        """Default: not implemented. Connectors override to enable."""
        raise NotImplementedError(f"{self.name.value} does not implement incremental sync yet.")
