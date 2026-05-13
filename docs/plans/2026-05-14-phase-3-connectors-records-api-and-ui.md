# Phase 3 — Connectors API + Records API + UI for a testable demo

> **For agentic workers:** This plan executes as **ONE subagent dispatch for the whole phase** (per `CLAUDE.md` workflow §3). The subagent works through all 8 tasks top-to-bottom, committing per task, and reports back when the phase is complete or blocked. Use `superpowers:subagent-driven-development`. Checkbox (`- [ ]`) syntax is for the subagent's own progress tracking.
>
> **Test discipline (per `docs/conventions.md §13.4`):** every test in this plan was filtered for meaningfulness. Each one fails on a real, harmful condition. If a test in this plan looks pointless after you read the implementation, **flag it back to the controller**, do not blindly write it. Do not add tests beyond the plan.

**Goal:** Turn the Phase 2 backend into a clickable demo. After this phase, a reviewer can open the app, click "Connect (demo)" on the Shopify card, click "Sync now", see the row count update, navigate to the Records page, click a row, and see the raw Shopify payload side-by-side with the normalized `Order` — proof of the universal schema + provenance contract end-to-end through the UI.

**Architecture:**
- Backend grows two new modules under `apps/api/src/munim/modules/`: `connectors/` (list, connect, sync endpoints) and `records/` (browse + drill-down endpoints). Both follow the vertical-slice pattern Phase 1 established for `health/`.
- A new `ConnectorRegistry` maps `ConnectorName` → `BaseConnector` instance. Adding Meta Ads / Shiprocket in Phase 4 is one registry entry per connector; routers and services don't change. This is the "swappable" part of "one interface, three implementations, swappable."
- The demo fixture moves from `apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json` to `apps/api/data/fixtures/shopify/orders.json` (matches `docs/architecture.md §14`) — production demo data, not test fixture. Tests get updated to point at the new path.
- Frontend gains `react-router-dom`, a layout shell with nav, and two new vertical-slice modules: `connectors/` and `records/`. Existing `health` module stays as a separate nav-less surface used only on the index page sidebar.
- The "connect" flow in Phase 3 is **demo-only**: `POST /api/connectors/shopify/connect` immediately writes a `ConnectorCredentials` row with `status='demo'` pointing at the fixture path. No OAuth dance. Real OAuth is Phase 7+ (separate plan).

**Tech stack additions:** `react-router-dom@7` on the frontend. No new backend deps — connectors and records are pure SQLModel queries through the existing engine.

**Out of scope (deliberate, called out so reviewers see what's not there yet):**
- Meta Ads + Shiprocket connectors (Phase 4 — same pattern, different mapper).
- Real OAuth flow with credential encryption (Phase 7).
- Records filter UI + pagination (returns first 50 rows server-side; add filter chips when chat needs them).
- Frontend unit tests (the demo is the test; component tests land in Phase 7 with the UI hardening pass).
- `run_log` writes from sync (Phase 6 wires this when the agent needs the log shape — for Phase 3 the sync endpoint returns the `SyncResult` envelope, no DB write).
- Toast notifications for sync feedback (use inline status text on the card for Phase 3; add a real toast primitive in Phase 7 if it's worth the bytes).
- Streaming sync progress over SSE (not needed at 3 rows; revisit if a real merchant has 50k orders and the sync runs for 30s).

---

## File map

**New files (with one-line responsibility):**

- `apps/api/data/fixtures/shopify/orders.json` — production demo fixture (moved from tests/fixtures).
- `apps/api/src/munim/connectors/registry.py` — `ConnectorRegistry`: name → connector instance.
- `apps/api/src/munim/connectors/tests/test_registry.py` — registry unit tests.
- `apps/api/src/munim/modules/connectors/__init__.py` — empty.
- `apps/api/src/munim/modules/connectors/schemas.py` — request/response Pydantic models.
- `apps/api/src/munim/modules/connectors/service.py` — business logic (list, connect, sync).
- `apps/api/src/munim/modules/connectors/router.py` — FastAPI routes.
- `apps/api/src/munim/modules/connectors/tests/__init__.py` — empty.
- `apps/api/src/munim/modules/connectors/tests/test_service.py` — service unit tests.
- `apps/api/src/munim/modules/connectors/tests/test_router.py` — router integration tests against TestClient.
- `apps/api/src/munim/modules/records/__init__.py` — empty.
- `apps/api/src/munim/modules/records/schemas.py` — request/response Pydantic models.
- `apps/api/src/munim/modules/records/service.py` — business logic (list, get by id).
- `apps/api/src/munim/modules/records/router.py` — FastAPI routes.
- `apps/api/src/munim/modules/records/tests/__init__.py` — empty.
- `apps/api/src/munim/modules/records/tests/test_service.py` — service tests.
- `apps/api/src/munim/modules/records/tests/test_router.py` — router tests.
- `apps/web/src/shared/components/Button.tsx` — reusable button primitive.
- `apps/web/src/shared/components/StatusBadge.tsx` — colored status badge.
- `apps/web/src/shared/components/EmptyState.tsx` — empty list placeholder.
- `apps/web/src/shared/components/AppShell.tsx` — header + nav + outlet layout.
- `apps/web/src/shared/components/NavLink.tsx` — styled router NavLink.
- `apps/web/src/router.tsx` — react-router-dom route tree.
- `apps/web/src/pages/IndexPage.tsx` — landing page (keeps HealthSection).
- `apps/web/src/pages/NotFoundPage.tsx` — 404.
- `apps/web/src/modules/connectors/__init__.ts` — re-export the page connector.
- `apps/web/src/modules/connectors/types/connector.types.ts` — Zod schemas + types.
- `apps/web/src/modules/connectors/api/connectors.api.ts` — ky calls.
- `apps/web/src/modules/connectors/hooks/useConnectors.ts` — list query.
- `apps/web/src/modules/connectors/hooks/useConnectMutation.ts` — POST connect.
- `apps/web/src/modules/connectors/hooks/useSyncMutation.ts` — POST sync.
- `apps/web/src/modules/connectors/components/ConnectorCard.tsx` — dumb card.
- `apps/web/src/modules/connectors/components/ConnectorsGrid.tsx` — dumb grid.
- `apps/web/src/modules/connectors/components/ConnectorsPage.tsx` — connector page.
- `apps/web/src/modules/connectors/index.ts` — re-export `ConnectorsPage`.
- `apps/web/src/modules/records/__init__.ts` — re-export the page connector.
- `apps/web/src/modules/records/types/record.types.ts` — Zod schemas + types.
- `apps/web/src/modules/records/api/records.api.ts` — ky calls.
- `apps/web/src/modules/records/hooks/useRecords.ts` — list query.
- `apps/web/src/modules/records/hooks/useRecord.ts` — single-record query.
- `apps/web/src/modules/records/components/RecordsTable.tsx` — dumb table.
- `apps/web/src/modules/records/components/RecordDrawer.tsx` — dumb raw/normalized drawer.
- `apps/web/src/modules/records/components/RecordsPage.tsx` — records page connector.
- `apps/web/src/modules/records/index.ts` — re-export `RecordsPage`.

**Modified files:**

- `apps/api/src/munim/connectors/shopify/tests/test_connector.py` — `FIXTURE_PATH` points to `data/fixtures/shopify/orders.json`.
- `apps/api/src/munim/connectors/shopify/tests/test_mapper.py` — same.
- `apps/api/src/munim/connectors/shopify/tests/test_client.py` — same.
- `apps/api/src/munim/main.py` — register the new routers.
- `apps/api/src/munim/shared/constants.py` — add `ErrorCode.CONNECTOR_UNKNOWN`, `ErrorCode.CONNECTOR_NOT_CONNECTED`, `ErrorCode.RECORD_NOT_FOUND`.
- `apps/web/package.json` — add `react-router-dom`.
- `apps/web/src/main.tsx` — wrap in `RouterProvider` instead of inline `<App />`.
- `apps/web/src/app.tsx` — delete (replaced by `AppShell` + router).
- `apps/web/src/modules/health/index.ts` — already exports `HealthSection`; re-used on `IndexPage`.

---

## Task 1 — Move the Shopify demo fixture to its production location

**Files:**
- Create: `apps/api/data/fixtures/shopify/orders.json` (moved content)
- Delete: `apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json`
- Modify: `apps/api/src/munim/connectors/shopify/tests/test_client.py`
- Modify: `apps/api/src/munim/connectors/shopify/tests/test_mapper.py`
- Modify: `apps/api/src/munim/connectors/shopify/tests/test_connector.py`

Why this task exists at all: `docs/architecture.md §14` says the demo fixture lives at `apps/api/data/fixtures/shopify/orders.json` (a production demo path, accessible from the running app). Phase 2's implementer put it inside `tests/fixtures/` because that was the test-local convention. Phase 3's demo endpoint needs a stable production path — one file, used by both tests and the running app.

- [ ] **Step 1: Move the fixture using git mv to preserve history**

Run (from repo root):
```
git mv apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json apps/api/data/fixtures/shopify/orders.json
```

If the parent dir doesn't exist yet, `git mv` will error. In that case, create the dir then move manually:
```
mkdir -p apps/api/data/fixtures/shopify
git mv apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json apps/api/data/fixtures/shopify/orders.json
```

- [ ] **Step 2: Update test paths**

Three test files reference the old path with `FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"`. Replace each with a helper that walks to the data dir.

Create a helper next to the tests at `apps/api/src/munim/connectors/shopify/tests/_paths.py`:
```python
"""Test helpers: paths used by all Shopify connector tests.

The demo fixture lives at apps/api/data/fixtures/shopify/orders.json — both
the running app (via the connect endpoint) and these tests read the same file.
"""

from pathlib import Path

# apps/api/src/munim/connectors/shopify/tests/_paths.py
# -> apps/api/
_API_ROOT = Path(__file__).parents[5]

SHOPIFY_DEMO_FIXTURE_PATH = _API_ROOT / "data" / "fixtures" / "shopify" / "orders.json"
```

Then in each of `test_client.py`, `test_mapper.py`, `test_connector.py`, replace the line:
```python
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"
```
with:
```python
from munim.connectors.shopify.tests._paths import SHOPIFY_DEMO_FIXTURE_PATH as FIXTURE_PATH
```

Leave every other line unchanged.

- [ ] **Step 3: Run the full backend suite to confirm no regressions**

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api'
uv run pytest -v
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```
Expected: 36 passed, all gates green.

- [ ] **Step 4: Commit**

```
git add apps/api
git commit -m "refactor(shopify): move demo fixture to apps/api/data/fixtures/shopify/ (production path)"
```

---

## Task 2 — `ConnectorRegistry`: name → connector instance

**Files:**
- Create: `apps/api/src/munim/connectors/registry.py`
- Create: `apps/api/src/munim/connectors/tests/test_registry.py`
- Modify: `apps/api/src/munim/shared/constants.py` (add new error codes)

- [ ] **Step 1: Add the new error codes**

In `apps/api/src/munim/shared/constants.py`, extend `ErrorCode`:
```python
class ErrorCode(StrEnum):
    SYSTEM_UNEXPECTED = "system.unexpected"
    SYSTEM_DATABASE_UNAVAILABLE = "system.database_unavailable"
    VALIDATION_MISSING_FIELD = "validation.missing_field"
    VALIDATION_BAD_FORMAT = "validation.bad_format"
    CONNECTOR_NOT_CONFIGURED = "connector.not_configured"
    CONNECTOR_SYNC_FAILED = "connector.sync_failed"
    CONNECTOR_UNKNOWN = "connector.unknown"
    CONNECTOR_NOT_CONNECTED = "connector.not_connected"
    RECORD_NOT_FOUND = "record.not_found"
```

- [ ] **Step 2: Write the failing tests first**

Create `apps/api/src/munim/connectors/tests/test_registry.py`:
```python
"""Registry tests. The registry is the seam where 'one interface, three
implementations, swappable' becomes provable. These tests fail when:
- The registry doesn't return the right concrete connector for a name.
- The registry silently returns None for an unknown name (silent fallback).
- A connector's `name` ClassVar disagrees with the registry key.
"""

import pytest

from munim.connectors.registry import (
    ConnectorRegistry,
    UnknownConnectorError,
    default_registry,
)
from munim.connectors.shopify.connector import ShopifyConnector
from munim.shared.constants import ConnectorName


def test_default_registry_resolves_shopify_to_shopify_connector() -> None:
    connector = default_registry().get(ConnectorName.SHOPIFY)
    assert isinstance(connector, ShopifyConnector)


def test_default_registry_lists_only_phase_3_connectors() -> None:
    # If a connector is added without a real impl, this test catches it before
    # a sync endpoint dispatches to a half-built connector.
    names = default_registry().names()
    assert ConnectorName.SHOPIFY in names


def test_registry_raises_typed_error_for_unknown_name() -> None:
    # Per docs/conventions.md §10 — no silent fallback (no `return None`).
    registry = ConnectorRegistry({})
    with pytest.raises(UnknownConnectorError) as exc_info:
        registry.get(ConnectorName.SHOPIFY)
    assert exc_info.value.code == "connector.unknown"


def test_registry_name_classvar_matches_registry_key() -> None:
    # Catches the bug where someone registers ShopifyConnector under the wrong
    # name string (e.g., "shoppify" typo) — the connector's own `name` is the
    # source of truth.
    registry = default_registry()
    for key in registry.names():
        assert registry.get(key).name is key
```

- [ ] **Step 3: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/connectors/tests/test_registry.py -v
```
Expected: ImportError on `from munim.connectors.registry import ...`.

- [ ] **Step 4: Implement the registry**

Create `apps/api/src/munim/connectors/registry.py`:
```python
"""Connector registry — the seam that makes the BaseConnector abstraction
swappable. A new connector becomes available to every endpoint by adding one
line to `default_registry()`. Routers and services never reference a concrete
connector class.

Per docs/conventions.md §10: unknown lookups raise — no silent fallback,
no None.
"""

from typing import Mapping

from munim.connectors.base import BaseConnector
from munim.connectors.shopify.connector import ShopifyConnector
from munim.shared.constants import ConnectorName
from munim.shared.errors import MunimError
from munim.shared.constants import ErrorCode


class UnknownConnectorError(MunimError):
    code = ErrorCode.CONNECTOR_UNKNOWN.value
    http_status = 404
    message = "Unknown connector."


class ConnectorRegistry:
    def __init__(self, connectors: Mapping[ConnectorName, BaseConnector]) -> None:
        self._connectors = dict(connectors)

    def get(self, name: ConnectorName) -> BaseConnector:
        connector = self._connectors.get(name)
        if connector is None:
            raise UnknownConnectorError(
                message=f"Connector {name.value!r} is not registered.",
                details={"connector": name.value, "known": [n.value for n in self._connectors]},
            )
        return connector

    def names(self) -> list[ConnectorName]:
        return list(self._connectors.keys())


def default_registry() -> ConnectorRegistry:
    """The production registry. Phase 4 adds Meta Ads + Shiprocket here."""
    return ConnectorRegistry(
        {
            ConnectorName.SHOPIFY: ShopifyConnector(),
        }
    )
```

- [ ] **Step 5: Run tests, see them pass**

```
uv run pytest src/munim/connectors/tests/test_registry.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Lint, typecheck, full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```
Expected: 40 passed total (36 from Phase 2 + 4 new).

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/connectors/registry.py apps/api/src/munim/connectors/tests/test_registry.py apps/api/src/munim/shared/constants.py
git commit -m "feat(connectors): add ConnectorRegistry — name → connector dispatch"
```

---

## Task 3 — `modules/connectors`: service + schemas

**Files:**
- Create: `apps/api/src/munim/modules/connectors/__init__.py` (empty)
- Create: `apps/api/src/munim/modules/connectors/schemas.py`
- Create: `apps/api/src/munim/modules/connectors/service.py`
- Create: `apps/api/src/munim/modules/connectors/tests/__init__.py` (empty)
- Create: `apps/api/src/munim/modules/connectors/tests/test_service.py`

The service has three operations:
1. `list_connectors(session, merchant_id)` — returns one entry per registered connector, with credential status + last_sync_at + per-entity record counts.
2. `connect_demo(session, merchant_id, name)` — creates (or upserts) a `ConnectorCredentials` row with `status='demo'` pointing at the demo fixture.
3. `sync(session, merchant_id, name)` — looks up the credential, dispatches to the connector via the registry, returns `SyncResult`.

- [ ] **Step 1: Write the schemas**

Create `apps/api/src/munim/modules/connectors/schemas.py`:
```python
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
```

- [ ] **Step 2: Write the failing service tests**

Create `apps/api/src/munim/modules/connectors/tests/test_service.py`:
```python
from sqlmodel import Session

from munim.connectors.registry import default_registry
from munim.modules.connectors.service import (
    connect_demo,
    list_connectors,
    sync_connector,
)
from munim.shared.constants import ConnectorName, CredentialStatus

DEFAULT_MERCHANT_ID = "m_default"


def test_list_connectors_returns_one_view_per_registered_connector(
    session: Session,
) -> None:
    # The list must mirror the registry exactly — if a registered connector
    # isn't in the response, the frontend can't surface it to the user.
    views = list_connectors(session, DEFAULT_MERCHANT_ID, default_registry())
    names = {v.name for v in views}
    assert names == set(default_registry().names())


def test_unconnected_connector_has_null_status_and_zero_counts(
    session: Session,
) -> None:
    # Fresh DB: no credentials, no records. The connector view must say so
    # honestly, not fall back to a "looks fine" default.
    [shopify_view] = [
        v
        for v in list_connectors(session, DEFAULT_MERCHANT_ID, default_registry())
        if v.name is ConnectorName.SHOPIFY
    ]
    assert shopify_view.status is None
    assert shopify_view.last_sync_at is None
    assert shopify_view.record_counts == []


def test_connect_demo_creates_credential_with_demo_status(
    session: Session,
) -> None:
    view = connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()
    assert view.status is CredentialStatus.DEMO


def test_connect_demo_is_idempotent_on_repeated_call(
    session: Session,
) -> None:
    # Clicking "Connect" twice must not create two credential rows — the
    # natural key (merchant_id, connector) is unique. Behaviour must be
    # explicit upsert, not silent error swallowing.
    connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()
    view_again = connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()
    assert view_again.status is CredentialStatus.DEMO


async def test_sync_writes_three_records_and_returns_meaningful_counts(
    session: Session,
) -> None:
    # End-to-end through the service: a sync after connect must produce
    # exactly three rows (fixture has 3 orders) and the SyncResult counts
    # must agree with the DB. If counts and DB disagree, every downstream
    # number on the UI is a lie.
    connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()

    result = await sync_connector(
        session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, default_registry()
    )
    session.commit()

    assert result.rows_upserted == 3
    assert result.rows_skipped == 0
    assert result.connector.status is CredentialStatus.DEMO
    counts = {c.entity_type: c.count for c in result.connector.record_counts}
    assert counts.get("order") == 3


async def test_sync_second_run_reports_three_skipped(session: Session) -> None:
    # The idempotency contract from Phase 2 must be observable at the API
    # surface, not just inside RowSink. If the UI says "3 rows synced" on
    # every click, users won't trust the system.
    connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()
    await sync_connector(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, default_registry())
    session.commit()
    second = await sync_connector(
        session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, default_registry()
    )
    session.commit()
    assert second.rows_upserted == 0
    assert second.rows_skipped == 3


async def test_sync_raises_when_credential_missing(session: Session) -> None:
    # Per docs/conventions.md §10: no silent fallback. Sync without a
    # credential must raise a typed error, not silently no-op or auto-create.
    from munim.modules.connectors.service import ConnectorNotConnectedError

    import pytest

    with pytest.raises(ConnectorNotConnectedError) as exc_info:
        await sync_connector(
            session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, default_registry()
        )
    assert exc_info.value.code == "connector.not_connected"
```

- [ ] **Step 3: Run tests, see them fail**

```
uv run pytest src/munim/modules/connectors/tests/test_service.py -v
```
Expected: ImportError.

- [ ] **Step 4: Implement the service**

Create `apps/api/src/munim/modules/connectors/service.py`:
```python
"""Connectors service. The router calls only into this module; this module
calls the registry + RowSink + connectors.base.

Demo credential blob shape:
    {"status": "demo", "fixture_path": "<absolute path to orders.json>"}.
"""

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import func
from sqlmodel import Session, col, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.registry import ConnectorRegistry
from munim.models import ConnectorCredentials, Record
from munim.modules.connectors.schemas import (
    ConnectorView,
    EntityCount,
    SyncResponse,
)
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    ErrorCode,
    SourceSystem,
)
from munim.shared.errors import MunimError

# apps/api/src/munim/modules/connectors/service.py
# -> apps/api/
_API_ROOT = Path(__file__).parents[5]


class ConnectorNotConnectedError(MunimError):
    code = ErrorCode.CONNECTOR_NOT_CONNECTED.value
    http_status = 409
    message = "Connector is not connected."


class ConnectorSyncError(MunimError):
    code = ErrorCode.CONNECTOR_SYNC_FAILED.value
    http_status = 500
    message = "Sync failed."


def list_connectors(
    session: Session,
    merchant_id: str,
    registry: ConnectorRegistry,
) -> list[ConnectorView]:
    return [
        _build_view(session, merchant_id, name)
        for name in registry.names()
    ]


def connect_demo(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
) -> ConnectorView:
    """Create or update a demo credential for `name`. Idempotent."""
    fixture_path = _resolve_demo_fixture_path(name)
    blob = {"status": CredentialStatus.DEMO.value, "fixture_path": str(fixture_path)}

    existing = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()

    if existing is None:
        session.add(
            ConnectorCredentials(
                merchant_id=merchant_id,
                connector=name.value,
                auth_blob_encrypted=json.dumps(blob),
                status=CredentialStatus.DEMO.value,
            )
        )
    else:
        existing.auth_blob_encrypted = json.dumps(blob)
        existing.status = CredentialStatus.DEMO.value
        session.add(existing)
    session.flush()  # so list_connectors below sees the new row

    return _build_view(session, merchant_id, name)


async def sync_connector(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    registry: ConnectorRegistry,
) -> SyncResponse:
    credential_row = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()
    if credential_row is None:
        raise ConnectorNotConnectedError(
            message=f"Connector {name.value!r} has no stored credential.",
            details={"connector": name.value},
        )

    credential = Credential(
        merchant_id=merchant_id,
        connector=name,
        blob=json.loads(credential_row.auth_blob_encrypted),
    )

    connector = registry.get(name)
    source_system = _connector_to_source(name)
    row_sink = RowSink(session, merchant_id, source_system)

    async with httpx.AsyncClient() as http_client:
        ctx = SyncContext(
            merchant_id=merchant_id,
            credential=credential,
            row_sink=row_sink,
            http_client=http_client,
        )
        result = await connector.sync_full(ctx)

    credential_row.last_sync_at = datetime.now(UTC)
    session.add(credential_row)
    session.flush()

    view = _build_view(session, merchant_id, name)
    return SyncResponse(
        rows_upserted=result.rows_upserted,
        rows_skipped=result.rows_skipped,
        started_at=result.started_at,
        finished_at=result.finished_at,
        connector=view,
    )


def _build_view(
    session: Session, merchant_id: str, name: ConnectorName
) -> ConnectorView:
    credential_row = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()

    counts = _record_counts(session, merchant_id, _connector_to_source(name))

    return ConnectorView(
        name=name,
        status=CredentialStatus(credential_row.status) if credential_row else None,
        last_sync_at=credential_row.last_sync_at if credential_row else None,
        record_counts=list(counts),
    )


def _record_counts(
    session: Session, merchant_id: str, source: SourceSystem
) -> Iterable[EntityCount]:
    rows = session.exec(
        select(Record.entity_type, func.count(col(Record.id)))
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == source.value)
        .group_by(Record.entity_type)
    ).all()
    return [EntityCount(entity_type=row[0], count=row[1]) for row in rows]


def _connector_to_source(name: ConnectorName) -> SourceSystem:
    return SourceSystem(name.value)


def _resolve_demo_fixture_path(name: ConnectorName) -> Path:
    return _API_ROOT / "data" / "fixtures" / name.value / "orders.json"
```

Note on the `_connector_to_source` shim: `ConnectorName` and `SourceSystem` are intentionally separate enums (per Phase 2 review nit) — they may diverge later when a webhook-based variant of a connector lands. The cast here is the single seam between them; if they ever diverge, this is the one place to update.

- [ ] **Step 5: Run service tests, see them pass**

```
uv run pytest src/munim/modules/connectors/tests/test_service.py -v
```
Expected: 7 passed.

- [ ] **Step 6: Full suite + lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```
Expected: 47 passed (40 from Task 2 + 7 new).

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/modules/connectors
git commit -m "feat(connectors): add list/connect-demo/sync service for /api/connectors"
```

---

## Task 4 — `modules/connectors`: router

**Files:**
- Create: `apps/api/src/munim/modules/connectors/router.py`
- Create: `apps/api/src/munim/modules/connectors/tests/test_router.py`
- Modify: `apps/api/src/munim/main.py` — register the router

- [ ] **Step 1: Write the failing router tests**

Create `apps/api/src/munim/modules/connectors/tests/test_router.py`:
```python
from fastapi.testclient import TestClient


def test_list_returns_envelope_with_shopify(client: TestClient) -> None:
    response = client.get("/connectors")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"].startswith("tr_")
    names = [c["name"] for c in body["data"]["connectors"]]
    assert "shopify" in names


def test_unconnected_shopify_status_is_null(client: TestClient) -> None:
    body = client.get("/connectors").json()
    shopify = next(c for c in body["data"]["connectors"] if c["name"] == "shopify")
    assert shopify["status"] is None
    assert shopify["last_sync_at"] is None


def test_connect_then_list_shows_demo_status(client: TestClient) -> None:
    client.post("/connectors/shopify/connect").raise_for_status()
    body = client.get("/connectors").json()
    shopify = next(c for c in body["data"]["connectors"] if c["name"] == "shopify")
    assert shopify["status"] == "demo"


def test_sync_returns_three_upserts_and_updates_counts(client: TestClient) -> None:
    # End-to-end at the HTTP boundary: connect → sync → counts visible.
    # If this passes, the demo works for a reviewer with no Python repl.
    client.post("/connectors/shopify/connect").raise_for_status()

    sync_response = client.post("/connectors/shopify/sync")
    assert sync_response.status_code == 200
    sync_body = sync_response.json()
    assert sync_body["data"]["rows_upserted"] == 3
    assert sync_body["data"]["rows_skipped"] == 0

    list_body = client.get("/connectors").json()
    shopify = next(c for c in list_body["data"]["connectors"] if c["name"] == "shopify")
    order_count = next(c["count"] for c in shopify["record_counts"] if c["entity_type"] == "order")
    assert order_count == 3
    assert shopify["last_sync_at"] is not None


def test_sync_without_connect_returns_typed_error_envelope(client: TestClient) -> None:
    # Per docs/conventions.md §10 — no silent fallback. The frontend branches
    # on `code`, so this must be 'connector.not_connected', not a generic 500.
    response = client.post("/connectors/shopify/sync")
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.not_connected"
    assert body["trace_id"].startswith("tr_")


def test_unknown_connector_name_returns_404_envelope(client: TestClient) -> None:
    response = client.post("/connectors/woocommerce/connect")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.unknown"
```

- [ ] **Step 2: Run tests, see them fail**

```
uv run pytest src/munim/modules/connectors/tests/test_router.py -v
```
Expected: 404s on every request (router not registered yet).

- [ ] **Step 3: Implement the router**

Create `apps/api/src/munim/modules/connectors/router.py`:
```python
"""HTTP routes for /connectors/*."""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from munim.connectors.registry import ConnectorRegistry, default_registry
from munim.modules.connectors.schemas import (
    ConnectorListResponse,
    ConnectResponse,
    SyncResponse,
)
from munim.modules.connectors.service import (
    connect_demo,
    list_connectors,
    sync_connector,
)
from munim.shared.constants import ConnectorName
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _registry_dep() -> ConnectorRegistry:
    return default_registry()


@router.get("", response_model=SuccessEnvelope[ConnectorListResponse])
def list_endpoint(
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[ConnectorListResponse]:
    connectors = list_connectors(session, DEFAULT_MERCHANT_ID, registry)
    return SuccessEnvelope(
        data=ConnectorListResponse(connectors=connectors),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/{name}/connect",
    response_model=SuccessEnvelope[ConnectResponse],
)
def connect_endpoint(
    name: ConnectorName,
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[ConnectResponse]:
    # Touch the registry so an unknown name raises before we write.
    registry.get(name)
    view = connect_demo(session, DEFAULT_MERCHANT_ID, name)
    session.commit()
    return SuccessEnvelope(
        data=ConnectResponse(connector=view),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/{name}/sync",
    response_model=SuccessEnvelope[SyncResponse],
)
async def sync_endpoint(
    name: ConnectorName,
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[SyncResponse]:
    registry.get(name)  # raise typed error if unknown
    result = await sync_connector(session, DEFAULT_MERCHANT_ID, name, registry)
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)
```

- [ ] **Step 4: Register the router in `main.py`**

Modify `apps/api/src/munim/main.py` — add the import and include the router:
```python
from munim.modules.connectors.router import router as connectors_router
# ... existing imports ...
```
Inside `create_app`:
```python
    app.include_router(health_router)
    app.include_router(connectors_router)
```

- [ ] **Step 5: Run router tests, see them pass**

```
uv run pytest src/munim/modules/connectors/tests/test_router.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Full suite + lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```
Expected: 53 passed (47 from Task 3 + 6 new).

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/modules/connectors apps/api/src/munim/main.py
git commit -m "feat(connectors): expose /api/connectors list/connect/sync endpoints"
```

---

## Task 5 — `modules/records`: service + router + tests

**Files:**
- Create: `apps/api/src/munim/modules/records/__init__.py` (empty)
- Create: `apps/api/src/munim/modules/records/schemas.py`
- Create: `apps/api/src/munim/modules/records/service.py`
- Create: `apps/api/src/munim/modules/records/router.py`
- Create: `apps/api/src/munim/modules/records/tests/__init__.py` (empty)
- Create: `apps/api/src/munim/modules/records/tests/test_router.py`
- Modify: `apps/api/src/munim/main.py` — register the router

- [ ] **Step 1: Schemas**

Create `apps/api/src/munim/modules/records/schemas.py`:
```python
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
```

- [ ] **Step 2: Service**

Create `apps/api/src/munim/modules/records/service.py`:
```python
from sqlmodel import Session, col, select

from munim.models import Record
from munim.modules.records.schemas import (
    RecordDetail,
    RecordSummary,
    RecordsListResponse,
    clamp_limit,
)
from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError


class RecordNotFoundError(MunimError):
    code = ErrorCode.RECORD_NOT_FOUND.value
    http_status = 404
    message = "Record not found."


def list_records(
    session: Session,
    merchant_id: str,
    *,
    source_system: str | None,
    entity_type: str | None,
    limit: int,
) -> RecordsListResponse:
    effective_limit = clamp_limit(limit)
    stmt = (
        select(Record)
        .where(Record.merchant_id == merchant_id)
        .order_by(col(Record.fetched_at).desc())
        .limit(effective_limit)
    )
    if source_system:
        stmt = stmt.where(Record.source_system == source_system)
    if entity_type:
        stmt = stmt.where(Record.entity_type == entity_type)

    rows = session.exec(stmt).all()
    items = [
        RecordSummary(
            id=r.id if r.id is not None else 0,
            source_system=r.source_system,
            source_id=r.source_id,
            entity_type=r.entity_type,
            fetched_at=r.fetched_at,
        )
        for r in rows
    ]
    return RecordsListResponse(items=items, limit=effective_limit)


def get_record(
    session: Session,
    merchant_id: str,
    record_id: int,
) -> RecordDetail:
    row = session.exec(
        select(Record).where(Record.id == record_id).where(Record.merchant_id == merchant_id)
    ).first()
    if row is None:
        raise RecordNotFoundError(
            message=f"Record {record_id} not found for this merchant.",
            details={"record_id": record_id},
        )
    return RecordDetail(
        id=row.id if row.id is not None else 0,
        source_system=row.source_system,
        source_id=row.source_id,
        entity_type=row.entity_type,
        fetched_at=row.fetched_at,
        payload_hash=row.payload_hash,
        raw=row.raw,
        normalized=row.normalized,
    )
```

- [ ] **Step 3: Router**

Create `apps/api/src/munim/modules/records/router.py`:
```python
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from munim.modules.records.schemas import (
    RecordDetail,
    RecordsListResponse,
)
from munim.modules.records.service import get_record, list_records
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=SuccessEnvelope[RecordsListResponse])
def list_endpoint(
    request: Request,
    source_system: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[RecordsListResponse]:
    data = list_records(
        session,
        DEFAULT_MERCHANT_ID,
        source_system=source_system,
        entity_type=entity_type,
        limit=limit,
    )
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.get("/{record_id}", response_model=SuccessEnvelope[RecordDetail])
def detail_endpoint(
    record_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[RecordDetail]:
    record = get_record(session, DEFAULT_MERCHANT_ID, record_id)
    return SuccessEnvelope(data=record, trace_id=request.state.trace_id)
```

- [ ] **Step 4: Register the router in `main.py`**

```python
from munim.modules.records.router import router as records_router
# ...
    app.include_router(connectors_router)
    app.include_router(records_router)
```

- [ ] **Step 5: Write the failing router tests**

Create `apps/api/src/munim/modules/records/tests/test_router.py`:
```python
from fastapi.testclient import TestClient


def _ensure_synced(client: TestClient) -> None:
    client.post("/connectors/shopify/connect").raise_for_status()
    client.post("/connectors/shopify/sync").raise_for_status()


def test_records_list_after_sync_returns_three_rows(client: TestClient) -> None:
    _ensure_synced(client)
    body = client.get("/records").json()
    assert body["success"] is True
    assert len(body["data"]["items"]) == 3
    assert {item["entity_type"] for item in body["data"]["items"]} == {"order"}


def test_records_list_filters_by_entity_type(client: TestClient) -> None:
    # Filter contract: the same query language used by chat tools later.
    # If a filter param is silently ignored, every later chat query is wrong.
    _ensure_synced(client)
    body = client.get("/records?entity_type=shipment").json()
    assert body["data"]["items"] == []


def test_records_detail_returns_raw_and_normalized(client: TestClient) -> None:
    # Provenance over HTTP: the raw column on the wire must equal the source
    # payload byte-for-byte, plus the normalized projection.
    _ensure_synced(client)
    list_body = client.get("/records").json()
    record_id = list_body["data"]["items"][0]["id"]

    detail = client.get(f"/records/{record_id}").json()
    assert detail["data"]["raw"]["id"] in (5510000000001, 5510000000002, 5510000000003)
    assert "total_inr" in detail["data"]["normalized"]
    assert detail["data"]["payload_hash"]


def test_records_detail_unknown_id_returns_typed_404(client: TestClient) -> None:
    response = client.get("/records/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "record.not_found"
```

- [ ] **Step 6: Run tests, see them pass**

```
uv run pytest src/munim/modules/records/tests/test_router.py -v
```
Expected: 4 passed.

- [ ] **Step 7: Full suite + lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```
Expected: 57 passed (53 + 4).

- [ ] **Step 8: Commit**

```
git add apps/api/src/munim/modules/records apps/api/src/munim/main.py
git commit -m "feat(records): expose /api/records list + detail endpoints"
```

---

## Task 6 — Frontend: router, shell, nav, shared primitives

**Files:**
- Modify: `apps/web/package.json` — add `react-router-dom`
- Create: `apps/web/src/router.tsx`
- Modify: `apps/web/src/main.tsx`
- Delete: `apps/web/src/app.tsx`
- Create: `apps/web/src/pages/IndexPage.tsx`
- Create: `apps/web/src/pages/NotFoundPage.tsx`
- Create: `apps/web/src/shared/components/AppShell.tsx`
- Create: `apps/web/src/shared/components/NavLink.tsx`
- Create: `apps/web/src/shared/components/Button.tsx`
- Create: `apps/web/src/shared/components/StatusBadge.tsx`
- Create: `apps/web/src/shared/components/EmptyState.tsx`
- Modify: `apps/web/src/shared/components/index.ts` — re-export new primitives

- [ ] **Step 1: Install react-router-dom**

In `apps/web/package.json`, add to `dependencies`:
```json
    "react-router-dom": "^7.1.0",
```

Then from `apps/web`:
```
pnpm install
```
Expected: install completes, no peer warnings that break the build.

- [ ] **Step 2: Add shared primitives**

Create `apps/web/src/shared/components/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  loading?: boolean;
  children: ReactNode;
}

const VARIANT_CLASS = {
  primary: 'bg-primary text-primary-fg hover:opacity-90 disabled:opacity-50',
  secondary: 'border border-border bg-bg-subtle text-fg hover:bg-bg-subtle/70',
  ghost: 'text-fg hover:bg-bg-subtle',
} as const;

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      {...rest}
      disabled={isDisabled}
      className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className ?? ''}`.trim()}
    >
      {loading && <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden />}
      {children}
    </button>
  );
}
```

Create `apps/web/src/shared/components/StatusBadge.tsx`:
```tsx
import type { ReactNode } from 'react';

interface StatusBadgeProps {
  tone: 'success' | 'warning' | 'error' | 'muted' | 'accent';
  children: ReactNode;
}

const TONE_CLASS = {
  success: 'bg-success/15 text-success border-success/30',
  warning: 'bg-warning/15 text-warning border-warning/40',
  error: 'bg-error/15 text-error border-error/30',
  muted: 'bg-bg-subtle text-muted border-border',
  accent: 'bg-accent/15 text-accent border-accent/30',
} as const;

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONE_CLASS[tone]}`}>
      {children}
    </span>
  );
}
```

Create `apps/web/src/shared/components/EmptyState.tsx`:
```tsx
import type { ReactNode } from 'react';

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium text-fg">{title}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
```

Create `apps/web/src/shared/components/NavLink.tsx`:
```tsx
import { NavLink as RouterNavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

interface NavLinkProps {
  to: string;
  disabled?: boolean;
  children: ReactNode;
}

const baseClass = 'rounded-md px-3 py-1.5 text-sm font-medium transition-colors';
const idleClass = 'text-muted hover:text-fg hover:bg-bg-subtle';
const activeClass = 'text-fg bg-bg-subtle';
const disabledClass = 'cursor-not-allowed text-muted/50';

export function NavLink({ to, disabled = false, children }: NavLinkProps) {
  if (disabled) {
    return <span className={`${baseClass} ${disabledClass}`}>{children}</span>;
  }
  return (
    <RouterNavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) => `${baseClass} ${isActive ? activeClass : idleClass}`}
    >
      {children}
    </RouterNavLink>
  );
}
```

Create `apps/web/src/shared/components/AppShell.tsx`:
```tsx
import { Outlet } from 'react-router-dom';

import { NavLink } from './NavLink';

export function AppShell() {
  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="border-b border-border bg-bg-subtle/40 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div>
            <h1 className="text-base font-semibold tracking-tight">AI-Munim</h1>
            <p className="text-xs text-muted">AI employee for D2C brands · v0</p>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink to="/">Overview</NavLink>
            <NavLink to="/connectors">Connectors</NavLink>
            <NavLink to="/records">Records</NavLink>
            <NavLink to="/chat" disabled>
              Chat · soon
            </NavLink>
            <NavLink to="/agent" disabled>
              Agent · soon
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
```

Re-export from `apps/web/src/shared/components/index.ts`:
```ts
export { Loader } from './Loader';
export { Card } from './Card';
export { Button } from './Button';
export { StatusBadge } from './StatusBadge';
export { EmptyState } from './EmptyState';
export { AppShell } from './AppShell';
export { NavLink } from './NavLink';
```

- [ ] **Step 3: Pages**

Create `apps/web/src/pages/IndexPage.tsx`:
```tsx
import { HealthSection } from '@/modules/health';

export function IndexPage() {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Overview</h2>
        <p className="mt-1 text-sm text-muted">
          One AI employee for D2C brands. Three connectors behind one abstraction. Citations on
          every number. Read the README before judging the build.
        </p>
      </section>
      <HealthSection />
    </div>
  );
}
```

Create `apps/web/src/pages/NotFoundPage.tsx`:
```tsx
export function NotFoundPage() {
  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium text-fg">Page not found</p>
      <p className="mt-1 text-xs text-muted">
        Try Overview, Connectors, or Records from the nav above.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Router**

Create `apps/web/src/router.tsx`:
```tsx
import { createBrowserRouter } from 'react-router-dom';

import { ConnectorsPage } from '@/modules/connectors';
import { RecordsPage } from '@/modules/records';
import { IndexPage } from '@/pages/IndexPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AppShell } from '@/shared/components';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <IndexPage /> },
      { path: 'connectors', element: <ConnectorsPage /> },
      { path: 'records', element: <RecordsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
```

(NOTE: `ConnectorsPage` and `RecordsPage` are added in Tasks 7 and 8. This file will fail to typecheck until those tasks complete. Don't try to lint/build between Task 6 and Task 7 — Task 7 + 8 land them, Task 8 step 6 is when the build runs green.)

- [ ] **Step 5: Wire main.tsx, delete app.tsx**

Replace `apps/web/src/main.tsx`:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';

import { router } from '@/router';
import { queryClient } from '@/shared/api';
import { ThemeProvider } from '@/shared/theme';

import './styles/globals.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found in index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
```

Delete `apps/web/src/app.tsx` (replaced by `AppShell` + router):
```
git rm apps/web/src/app.tsx
```

- [ ] **Step 6: Commit (build NOT expected to pass yet)**

Tasks 7 and 8 add the page modules; the build will fail until then. This commit is OK as a checkpoint:

```
git add apps/web
git commit -m "feat(web): add react-router-dom, AppShell, shared primitives (build wired after Tasks 7-8)"
```

---

## Task 7 — Frontend: `modules/connectors` (api, hooks, components, page)

**Files:**
- Create: `apps/web/src/modules/connectors/types/connector.types.ts`
- Create: `apps/web/src/modules/connectors/api/connectors.api.ts`
- Create: `apps/web/src/modules/connectors/hooks/useConnectors.ts`
- Create: `apps/web/src/modules/connectors/hooks/useConnectMutation.ts`
- Create: `apps/web/src/modules/connectors/hooks/useSyncMutation.ts`
- Create: `apps/web/src/modules/connectors/components/ConnectorCard.tsx`
- Create: `apps/web/src/modules/connectors/components/ConnectorsGrid.tsx`
- Create: `apps/web/src/modules/connectors/components/ConnectorsPage.tsx`
- Create: `apps/web/src/modules/connectors/index.ts`

- [ ] **Step 1: Types (Zod schemas mirroring the backend)**

Create `apps/web/src/modules/connectors/types/connector.types.ts`:
```ts
import { z } from 'zod';

export const ConnectorName = {
  Shopify: 'shopify',
  MetaAds: 'meta_ads',
  Shiprocket: 'shiprocket',
} as const;
export type ConnectorName = (typeof ConnectorName)[keyof typeof ConnectorName];

export const CredentialStatus = {
  Connected: 'connected',
  Demo: 'demo',
  Error: 'error',
} as const;
export type CredentialStatus = (typeof CredentialStatus)[keyof typeof CredentialStatus];

export const entityCountSchema = z.object({
  entity_type: z.string(),
  count: z.number().int().nonnegative(),
});

export const connectorViewSchema = z.object({
  name: z.enum(['shopify', 'meta_ads', 'shiprocket']),
  status: z.enum(['connected', 'demo', 'error']).nullable(),
  last_sync_at: z.string().nullable(),
  record_counts: z.array(entityCountSchema),
});

export const connectorListResponseSchema = z.object({
  connectors: z.array(connectorViewSchema),
});

export const connectResponseSchema = z.object({
  connector: connectorViewSchema,
});

export const syncResponseSchema = z.object({
  rows_upserted: z.number().int().nonnegative(),
  rows_skipped: z.number().int().nonnegative(),
  started_at: z.string(),
  finished_at: z.string(),
  connector: connectorViewSchema,
});

export type EntityCount = z.infer<typeof entityCountSchema>;
export type ConnectorView = z.infer<typeof connectorViewSchema>;
export type ConnectorListResponse = z.infer<typeof connectorListResponseSchema>;
export type ConnectResponse = z.infer<typeof connectResponseSchema>;
export type SyncResponse = z.infer<typeof syncResponseSchema>;
```

- [ ] **Step 2: API**

Create `apps/web/src/modules/connectors/api/connectors.api.ts`:
```ts
import { apiGet, apiPost, type ApiResponse } from '@/shared/api';

import {
  connectorListResponseSchema,
  connectResponseSchema,
  syncResponseSchema,
  type ConnectorListResponse,
  type ConnectorName,
  type ConnectResponse,
  type SyncResponse,
} from '../types/connector.types';

export const CONNECTORS_QUERY_KEY = ['connectors'] as const;

export function fetchConnectors(): Promise<ApiResponse<ConnectorListResponse>> {
  return apiGet('/connectors', connectorListResponseSchema);
}

export function postConnect(name: ConnectorName): Promise<ApiResponse<ConnectResponse>> {
  return apiPost(`/connectors/${name}/connect`, connectResponseSchema);
}

export function postSync(name: ConnectorName): Promise<ApiResponse<SyncResponse>> {
  return apiPost(`/connectors/${name}/sync`, syncResponseSchema);
}
```

- [ ] **Step 3: Hooks**

Create `apps/web/src/modules/connectors/hooks/useConnectors.ts`:
```ts
import { useQuery } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, fetchConnectors } from '../api/connectors.api';

export function useConnectors() {
  const query = useQuery({
    queryKey: CONNECTORS_QUERY_KEY,
    queryFn: fetchConnectors,
  });
  return {
    connectors: query.data?.data.connectors,
    traceId: query.data?.traceId,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
```

Create `apps/web/src/modules/connectors/hooks/useConnectMutation.ts`:
```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, postConnect } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

export function useConnectMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postConnect(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
    },
  });
}
```

Create `apps/web/src/modules/connectors/hooks/useSyncMutation.ts`:
```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { CONNECTORS_QUERY_KEY, postSync } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

const RECORDS_QUERY_KEY = ['records'];

export function useSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: ConnectorName) => postSync(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONNECTORS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: RECORDS_QUERY_KEY });
    },
  });
}
```

- [ ] **Step 4: Components**

Create `apps/web/src/modules/connectors/components/ConnectorCard.tsx`:
```tsx
import { Button, Card, StatusBadge } from '@/shared/components';

import type { ConnectorView, ConnectorName, CredentialStatus } from '../types/connector.types';

interface ConnectorCardProps {
  view: ConnectorView;
  connecting: boolean;
  syncing: boolean;
  onConnect: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

const STATUS_TONE: Record<CredentialStatus, 'success' | 'accent' | 'error'> = {
  connected: 'success',
  demo: 'accent',
  error: 'error',
};

const LABELS: Record<ConnectorName, string> = {
  shopify: 'Shopify',
  meta_ads: 'Meta Ads',
  shiprocket: 'Shiprocket',
};

export function ConnectorCard({
  view,
  connecting,
  syncing,
  onConnect,
  onSync,
}: ConnectorCardProps) {
  const isConnected = view.status !== null;
  const orderCount = view.record_counts.find((c) => c.entity_type === 'order')?.count ?? 0;

  return (
    <Card
      title={LABELS[view.name as ConnectorName] ?? view.name}
      trailing={
        view.status ? (
          <StatusBadge tone={STATUS_TONE[view.status]}>{view.status}</StatusBadge>
        ) : (
          <StatusBadge tone="muted">not connected</StatusBadge>
        )
      }
    >
      <div className="space-y-4 text-sm">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
          <dt className="text-muted">Orders synced</dt>
          <dd className="font-mono">{orderCount}</dd>
          <dt className="text-muted">Last sync</dt>
          <dd className="font-mono">{view.last_sync_at ?? '—'}</dd>
        </dl>
        <div className="flex gap-2">
          {!isConnected && (
            <Button onClick={() => onConnect(view.name as ConnectorName)} loading={connecting}>
              Connect (demo)
            </Button>
          )}
          {isConnected && (
            <Button
              variant="secondary"
              onClick={() => onSync(view.name as ConnectorName)}
              loading={syncing}
            >
              Sync now
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
```

Create `apps/web/src/modules/connectors/components/ConnectorsGrid.tsx`:
```tsx
import { Loader } from '@/shared/components';

import { ConnectorCard } from './ConnectorCard';
import type { ConnectorName, ConnectorView } from '../types/connector.types';

interface ConnectorsGridProps {
  connectors: ConnectorView[] | undefined;
  isLoading: boolean;
  error: Error | null;
  connectingName: ConnectorName | null;
  syncingName: ConnectorName | null;
  onConnect: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

export function ConnectorsGrid({
  connectors,
  isLoading,
  error,
  connectingName,
  syncingName,
  onConnect,
  onSync,
}: ConnectorsGridProps) {
  if (isLoading) return <Loader label="Loading connectors…" />;
  if (error) {
    return (
      <div className="rounded-md border border-error/30 bg-error/10 p-4 text-sm text-error">
        <p className="font-medium">Could not load connectors</p>
        <p className="mt-1 font-mono text-xs">{error.message}</p>
      </div>
    );
  }
  if (!connectors || connectors.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {connectors.map((view) => (
        <ConnectorCard
          key={view.name}
          view={view}
          connecting={connectingName === view.name}
          syncing={syncingName === view.name}
          onConnect={onConnect}
          onSync={onSync}
        />
      ))}
    </div>
  );
}
```

Create `apps/web/src/modules/connectors/components/ConnectorsPage.tsx`:
```tsx
import { useState } from 'react';

import { useConnectMutation } from '../hooks/useConnectMutation';
import { useConnectors } from '../hooks/useConnectors';
import { useSyncMutation } from '../hooks/useSyncMutation';
import type { ConnectorName, SyncResponse } from '../types/connector.types';
import { ConnectorsGrid } from './ConnectorsGrid';

export function ConnectorsPage() {
  const { connectors, isLoading, error } = useConnectors();
  const connect = useConnectMutation();
  const sync = useSyncMutation();
  const [lastSync, setLastSync] = useState<SyncResponse | null>(null);

  const handleConnect = (name: ConnectorName) => {
    connect.mutate(name);
  };
  const handleSync = (name: ConnectorName) => {
    sync.mutate(name, {
      onSuccess: (resp) => setLastSync(resp.data),
    });
  };

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Connectors</h2>
        <p className="mt-1 text-sm text-muted">
          Three connectors behind one abstraction. Click <em>Connect (demo)</em> to load a frozen
          fixture, then <em>Sync now</em> to upsert into the universal <code>record</code> table.
        </p>
      </section>

      <ConnectorsGrid
        connectors={connectors}
        isLoading={isLoading}
        error={error}
        connectingName={connect.isPending ? (connect.variables ?? null) : null}
        syncingName={sync.isPending ? (sync.variables ?? null) : null}
        onConnect={handleConnect}
        onSync={handleSync}
      />

      {lastSync && (
        <div className="rounded-md border border-success/30 bg-success/10 p-4 text-sm">
          <p className="font-medium text-success">
            Sync complete: {lastSync.rows_upserted} upserted, {lastSync.rows_skipped} unchanged.
          </p>
          <p className="mt-1 text-xs text-muted">
            Open the Records tab to inspect the rows + their original Shopify payloads.
          </p>
        </div>
      )}
    </div>
  );
}
```

Create `apps/web/src/modules/connectors/index.ts`:
```ts
export { ConnectorsPage } from './components/ConnectorsPage';
```

- [ ] **Step 5: Commit (still pre-Records-page; build NOT expected to pass yet)**

```
git add apps/web/src/modules/connectors
git commit -m "feat(web): connectors module — list/connect/sync UI"
```

---

## Task 8 — Frontend: `modules/records` (api, hooks, components, page) + final build

**Files:**
- Create: `apps/web/src/modules/records/types/record.types.ts`
- Create: `apps/web/src/modules/records/api/records.api.ts`
- Create: `apps/web/src/modules/records/hooks/useRecords.ts`
- Create: `apps/web/src/modules/records/hooks/useRecord.ts`
- Create: `apps/web/src/modules/records/components/RecordsTable.tsx`
- Create: `apps/web/src/modules/records/components/RecordDrawer.tsx`
- Create: `apps/web/src/modules/records/components/RecordsPage.tsx`
- Create: `apps/web/src/modules/records/index.ts`

- [ ] **Step 1: Types**

Create `apps/web/src/modules/records/types/record.types.ts`:
```ts
import { z } from 'zod';

export const recordSummarySchema = z.object({
  id: z.number().int(),
  source_system: z.string(),
  source_id: z.string(),
  entity_type: z.string(),
  fetched_at: z.string(),
});

export const recordDetailSchema = z.object({
  id: z.number().int(),
  source_system: z.string(),
  source_id: z.string(),
  entity_type: z.string(),
  fetched_at: z.string(),
  payload_hash: z.string(),
  raw: z.record(z.unknown()),
  normalized: z.record(z.unknown()),
});

export const recordsListResponseSchema = z.object({
  items: z.array(recordSummarySchema),
  limit: z.number().int(),
});

export type RecordSummary = z.infer<typeof recordSummarySchema>;
export type RecordDetail = z.infer<typeof recordDetailSchema>;
export type RecordsListResponse = z.infer<typeof recordsListResponseSchema>;
```

- [ ] **Step 2: API**

Create `apps/web/src/modules/records/api/records.api.ts`:
```ts
import { apiGet, type ApiResponse } from '@/shared/api';

import {
  recordDetailSchema,
  recordsListResponseSchema,
  type RecordDetail,
  type RecordsListResponse,
} from '../types/record.types';

export const RECORDS_LIST_QUERY_KEY = ['records'] as const;
export const RECORD_DETAIL_QUERY_KEY = (id: number) => ['records', id] as const;

export function fetchRecords(): Promise<ApiResponse<RecordsListResponse>> {
  return apiGet('/records', recordsListResponseSchema);
}

export function fetchRecord(id: number): Promise<ApiResponse<RecordDetail>> {
  return apiGet(`/records/${id}`, recordDetailSchema);
}
```

- [ ] **Step 3: Hooks**

Create `apps/web/src/modules/records/hooks/useRecords.ts`:
```ts
import { useQuery } from '@tanstack/react-query';

import { RECORDS_LIST_QUERY_KEY, fetchRecords } from '../api/records.api';

export function useRecords() {
  const query = useQuery({
    queryKey: RECORDS_LIST_QUERY_KEY,
    queryFn: fetchRecords,
  });
  return {
    items: query.data?.data.items,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
```

Create `apps/web/src/modules/records/hooks/useRecord.ts`:
```ts
import { useQuery } from '@tanstack/react-query';

import { RECORD_DETAIL_QUERY_KEY, fetchRecord } from '../api/records.api';

export function useRecord(id: number | null) {
  const query = useQuery({
    queryKey: RECORD_DETAIL_QUERY_KEY(id ?? -1),
    queryFn: () => {
      if (id === null) {
        throw new Error('useRecord called with null id — guard with `enabled` instead.');
      }
      return fetchRecord(id);
    },
    enabled: id !== null,
  });
  return {
    record: query.data?.data,
    isLoading: query.isLoading,
    error: query.error,
  };
}
```

- [ ] **Step 4: Components**

Create `apps/web/src/modules/records/components/RecordsTable.tsx`:
```tsx
import { EmptyState } from '@/shared/components';

import type { RecordSummary } from '../types/record.types';

interface RecordsTableProps {
  items: RecordSummary[];
  onRowClick: (id: number) => void;
}

export function RecordsTable({ items, onRowClick }: RecordsTableProps) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No records yet"
        hint="Go to Connectors, hit Connect (demo), then Sync now."
      />
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-bg-subtle text-xs uppercase text-muted">
          <tr>
            <th className="px-4 py-2 font-medium">Source</th>
            <th className="px-4 py-2 font-medium">Source ID</th>
            <th className="px-4 py-2 font-medium">Entity</th>
            <th className="px-4 py-2 font-medium">Fetched</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="cursor-pointer border-t border-border hover:bg-bg-subtle/50"
              onClick={() => onRowClick(item.id)}
            >
              <td className="px-4 py-2">{item.source_system}</td>
              <td className="px-4 py-2 font-mono text-xs">{item.source_id}</td>
              <td className="px-4 py-2">{item.entity_type}</td>
              <td className="px-4 py-2 text-xs text-muted">{item.fetched_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Create `apps/web/src/modules/records/components/RecordDrawer.tsx`:
```tsx
import { Button, Loader } from '@/shared/components';

import type { RecordDetail } from '../types/record.types';

interface RecordDrawerProps {
  record: RecordDetail | undefined;
  isLoading: boolean;
  error: Error | null;
  onClose: () => void;
}

export function RecordDrawer({ record, isLoading, error, onClose }: RecordDrawerProps) {
  return (
    <aside className="fixed inset-y-0 right-0 w-[600px] max-w-[90vw] overflow-y-auto border-l border-border bg-bg shadow-xl">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div>
          <h3 className="text-base font-semibold">Record detail</h3>
          {record && (
            <p className="font-mono text-xs text-muted">
              {record.source_system} · {record.source_id}
            </p>
          )}
        </div>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </header>
      <div className="space-y-6 px-6 py-4">
        {isLoading && <Loader label="Loading record…" />}
        {error && <p className="text-sm text-error">{error.message}</p>}
        {record && (
          <>
            <section>
              <h4 className="text-xs font-semibold uppercase text-muted">Normalized</h4>
              <pre className="mt-2 overflow-x-auto rounded-md bg-bg-subtle p-3 text-xs">
                {JSON.stringify(record.normalized, null, 2)}
              </pre>
            </section>
            <section>
              <h4 className="text-xs font-semibold uppercase text-muted">
                Raw (provenance — exact Shopify payload)
              </h4>
              <pre className="mt-2 overflow-x-auto rounded-md bg-bg-subtle p-3 text-xs">
                {JSON.stringify(record.raw, null, 2)}
              </pre>
            </section>
            <section className="text-xs text-muted">
              <p>
                <span className="font-mono">payload_hash:</span> {record.payload_hash}
              </p>
              <p>
                <span className="font-mono">fetched_at:</span> {record.fetched_at}
              </p>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
```

Create `apps/web/src/modules/records/components/RecordsPage.tsx`:
```tsx
import { useState } from 'react';

import { Loader } from '@/shared/components';

import { useRecord } from '../hooks/useRecord';
import { useRecords } from '../hooks/useRecords';
import { RecordDrawer } from './RecordDrawer';
import { RecordsTable } from './RecordsTable';

export function RecordsPage() {
  const { items, isLoading, error } = useRecords();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { record, isLoading: detailLoading, error: detailError } = useRecord(selectedId);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Records</h2>
        <p className="mt-1 text-sm text-muted">
          Universal storage. Every row carries its source, the original raw payload, and our
          normalized projection. Click a row to see both side by side.
        </p>
      </section>

      {isLoading && <Loader label="Loading records…" />}
      {error && (
        <div className="rounded-md border border-error/30 bg-error/10 p-4 text-sm text-error">
          <p className="font-medium">Could not load records</p>
          <p className="mt-1 font-mono text-xs">{error.message}</p>
        </div>
      )}
      {items && <RecordsTable items={items} onRowClick={setSelectedId} />}

      {selectedId !== null && (
        <RecordDrawer
          record={record}
          isLoading={detailLoading}
          error={detailError}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
```

Create `apps/web/src/modules/records/index.ts`:
```ts
export { RecordsPage } from './components/RecordsPage';
```

- [ ] **Step 5: Final build verification**

```
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\web'
pnpm typecheck
pnpm lint
pnpm build
```
Expected: typecheck green, lint clean, build succeeds (<2s).

- [ ] **Step 6: Commit**

```
git add apps/web/src/modules/records
git commit -m "feat(web): records module — table + raw/normalized drawer"
```

---

## Task 9 — Update `CHANGELOG.md` + `context.md`, manual smoke instructions, final commit

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `context.md`

- [ ] **Step 1: CHANGELOG entry**

Insert at the top of `CHANGELOG.md`:
```
## 2026-05-14 — Phase 3: connectors API + records API + clickable demo UI

**What changed:** Added two new vertical-slice backend modules — `connectors` (list/connect/sync endpoints) and `records` (list/detail) — plus `ConnectorRegistry` so adding Meta Ads / Shiprocket in Phase 4 is one registry entry. Moved the Shopify demo fixture from `tests/fixtures/` to `apps/api/data/fixtures/shopify/` (production demo path). Frontend gained `react-router-dom`, an `AppShell` with nav, and two new vertical-slice modules — `connectors` (Connect / Sync UI per card) and `records` (table + drawer showing raw + normalized side by side). The demo is now clickable: Connect → Sync → Records → row → see provenance.

**Files touched:** `apps/api/src/munim/connectors/registry.py`, `apps/api/src/munim/modules/connectors/*`, `apps/api/src/munim/modules/records/*`, `apps/api/data/fixtures/shopify/orders.json`, `apps/web/src/router.tsx`, `apps/web/src/pages/*`, `apps/web/src/modules/connectors/*`, `apps/web/src/modules/records/*`, `apps/web/src/shared/components/*`.

**Reverts cleanly?:** yes — the new modules can be deleted; revert the fixture move + `main.py` router registration + `main.tsx` to drop the phase.
```

- [ ] **Step 2: Update `context.md`**

In `context.md`:
- **Now** → "Phase 3 complete. Clickable demo: Connect → Sync → Records → row → raw + normalized side by side. 57 backend tests green."
- **Done** → append: "2026-05-14 — **Phase 3 complete.** Connectors + Records API, AppShell + nav, two new frontend modules. End-to-end demo working at `/connectors` and `/records`."
- **Next** → bump Phase 4 to top: "Phase 4 — Connectors 2 and 3 (Meta Ads + Shiprocket): same pattern, register in `default_registry`, add demo fixtures."
- **Decisions** → append:
  ```
  ### 2026-05-14 — Demo fixture lives at apps/api/data/fixtures/, not in tests/

  **Decision:** Moved the Shopify orders fixture from `tests/fixtures/` to
  `apps/api/data/fixtures/shopify/orders.json`. Tests now point at the same
  file via a small `_paths.py` helper.

  **Why:** The running app's connect endpoint needs a stable path that isn't
  inside a tests directory. One file used by both demo and tests beats two
  copies that can drift apart.

  **Revisit if:** the fixture grows to MB scale and slows test discovery, or
  if we want test-specific edge cases that shouldn't pollute the demo.
  ```

- [ ] **Step 3: Final smoke for the operator (the user, not the subagent)**

This step doesn't change code; it's the manual-test recipe to include in the final commit body so the operator knows what to verify.

The smoke recipe (use exactly these commands when running locally):
```
# Shell 1 — backend
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api'
uv run uvicorn munim.main:app --reload --port 8000

# Shell 2 — frontend
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\web'
pnpm dev
```
Then in a browser at `http://localhost:5173`:
1. **Overview** page shows `Status: ok / Version: 0.1.0` with a `tr_...` trace_id (Phase 1 health, unchanged).
2. **Connectors** tab → Shopify card shows `not connected`, `Orders synced: 0`, `Last sync: —`, and a `Connect (demo)` button.
3. Click `Connect (demo)` → button briefly shows a spinner → card now shows `demo` badge and a `Sync now` button.
4. Click `Sync now` → spinner → confirmation strip below the grid: `Sync complete: 3 upserted, 0 unchanged.` Card now shows `Orders synced: 3` and a `last_sync_at` timestamp.
5. Click `Sync now` again → strip updates to `0 upserted, 3 unchanged.` (idempotency proof.)
6. **Records** tab → table with 3 rows; each row shows `shopify / <order id> / order / <timestamp>`.
7. Click any row → drawer slides in from the right with two JSON blocks: `Normalized` and `Raw (provenance — exact Shopify payload)`. The raw block is byte-equal to the fixture's Shopify response.
8. Backend shell logs every request as one JSON line with `trace_id` auto-bound (`{"event": "...", "trace_id": "tr_...", ...}`).
9. DevTools → Network → click `/api/connectors` row → response has `x-trace-id` header matching the body's `trace_id`.

- [ ] **Step 4: Final commit**

```
git add CHANGELOG.md context.md
git commit -m "$(cat <<'EOF'
docs(phase-3): record Phase 3 completion + clickable demo smoke recipe

Phase 3 ships a clickable demo: Connect → Sync → Records → row → raw +
normalized side by side. Backend 57 tests green; frontend typecheck +
lint + build clean.

Manual smoke recipe (open http://localhost:5173):
1. Overview shows Status: ok / Version: 0.1.0 with a tr_ trace_id.
2. Connectors → Shopify shows 'not connected', click Connect (demo).
3. Card flips to 'demo' badge. Click Sync now → 3 upserted, 0 unchanged.
4. Click Sync now again → 0 upserted, 3 unchanged (idempotency).
5. Records tab → table of 3 rows. Click a row → drawer with raw +
   normalized JSON side by side. raw is byte-equal to the source.
6. Every backend request logs one JSON line with trace_id auto-bound;
   X-Trace-Id response header matches the body.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage check (against the brief):**
- Connector abstraction (one interface, three implementations, swappable) → `ConnectorRegistry` is the swappable seam. Demonstrated with 1 of 3 connectors live (Shopify); Meta + Shiprocket are 1 line each in Phase 4.
- Universal schema + provenance → exposed via `/api/records/{id}` returning `raw` + `normalized`, surfaced in UI drawer.
- Demo without API keys → Connect button creates demo credential; no env keys required.
- Brief's "We'll see [speed] in your commit history" → 9 conventional commits, one per task.

**§13.4 filter applied to every test:** all tests assert real invariants (idempotent sync counts, typed error envelope on missing credential, raw payload byte-equal on the wire, unique constraint enforcement at the API surface). No assertions that pass with `pass`.

**Type/name consistency check:**
- `ConnectorView` shape is defined in backend `schemas.py` and mirrored in frontend Zod `connectorViewSchema`. Both have `name`, `status`, `last_sync_at`, `record_counts`. ✓
- `SyncResponse` mirrors flat: `rows_upserted`, `rows_skipped`, `started_at`, `finished_at`, `connector`. ✓
- `RecordSummary` / `RecordDetail` shapes line up between backend Pydantic and frontend Zod. ✓
- Error codes used in tests (`connector.not_connected`, `connector.unknown`, `record.not_found`) match the `ErrorCode` enum entries added in Task 2 Step 1. ✓

**Placeholder scan:** none. Every step has actual code or an exact command. The deliberate "this commit will not pass `pnpm build` yet" notes in Tasks 6 and 7 are the only break in the green-after-every-commit pattern — Task 8 Step 5 is the green gate for the frontend.

**Out-of-scope deliberately re-listed:** Meta + Shiprocket connectors (Phase 4), real OAuth + credential encryption (Phase 7), filter UI (Phase 7 if needed), `run_log` writes from sync (Phase 6 when agent needs the shape), pagination (Phase 7 if needed), frontend unit tests (Phase 7).
