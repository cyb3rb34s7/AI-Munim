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

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict

from munim.shared.constants import ConnectorName

if TYPE_CHECKING:
    from munim.connectors._row_sink import RowSink


class Credential(BaseModel):
    """Opaque credential bag passed from the credential store into a connector.

    The connector decides how to interpret `blob`. Demo mode uses:
        {"status": "demo", "fixture_path": "<absolute path>"}.

    `extra="forbid"` catches typos in the outer keys (`merchant_id`,
    `connector`, `blob`). Anything connector-specific belongs inside `blob`.
    """

    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    connector: ConnectorName
    blob: dict[str, Any]


class SyncResult(BaseModel):
    """Outcome of one sync run. Returned by `sync_full` / `sync_incremental`.

    Fields:
      - `rows_upserted`: rows inserted or whose `payload_hash` changed.
      - `rows_skipped`: rows whose `payload_hash` matched the stored row,
        so no DB write was needed (idempotency proof).
      - `started_at` / `finished_at`: UTC-aware datetimes bracketing the run.
      - `errors`: list of per-row error messages. Phase 2 lets exceptions
        propagate (no per-row swallow), so this stays empty. Phase 3 may
        wire per-row error capture when an API endpoint needs partial-success
        results — adding entries here will be intentional then, not silent.

    `extra="forbid"` ensures a typo in any of the above field names raises
    at construction rather than silently producing a zero-default count.
    """

    model_config = ConfigDict(extra="forbid")

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
    row_sink: RowSink
    http_client: httpx.AsyncClient
    cursor: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """Every source-specific connector implements this contract.

    `is_demo` declares whether the connector ships a fixture-backed sync. Real
    connectors set it to False (default); demo connectors override to True and
    must be reachable via `POST /connectors/{name}/connect-demo`.
    """

    name: ClassVar[ConnectorName]
    is_demo: ClassVar[bool] = False

    @abstractmethod
    async def validate(self, credential: Credential) -> bool:
        """Quick credential health check."""

    @abstractmethod
    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        """Full backfill from the source."""

    async def sync_incremental(self, ctx: SyncContext) -> SyncResult:
        """Default: not implemented. Connectors override to enable."""
        raise NotImplementedError(f"{self.name.value} does not implement incremental sync yet.")
