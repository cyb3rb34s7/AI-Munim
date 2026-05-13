# Phase 2 — Universal Schema + Shopify Connector Implementation Plan

> **For agentic workers:** This plan executes as **ONE subagent dispatch for the whole phase** (per `CLAUDE.md` workflow §3 — one coder per phase, not per task). The subagent works through all 10 tasks top-to-bottom, committing per task per the plan, and reports back when the phase is complete or blocked. Use `superpowers:subagent-driven-development`. Checkbox (`- [ ]`) syntax is for the subagent's own progress tracking.
>
> **Test discipline (per `docs/conventions.md §13.4`):** every test in this plan was filtered for meaningfulness. Each one fails on a real, harmful condition. **If you (the subagent) find yourself about to write an additional test that just re-asserts a type or stores-and-reads-back without an invariant, stop. Don't add it.** If a test in this plan looks pointless after you read the implementation, raise it — don't write noise.

**Goal:** Wire the universal 4-table schema, the `BaseConnector` abstraction, and the first connector (Shopify) running end-to-end against a frozen demo fixture — proving the source-API → normalized Pydantic → `record` row + provenance flow without needing real OAuth or a real Shopify store.

**Architecture:** Single-table polymorphic storage (`record` discriminated by `entity_type`); typed entity shapes are Pydantic models under `apps/api/src/munim/schemas/`; connectors are stateless classes implementing `BaseConnector`; the only thing that writes to the `record` table is the `RowSink`, which stamps provenance fields automatically and enforces upsert on the natural key `(merchant_id, source_system, source_id)`.

**Tech stack:** SQLModel for SQL tables (sync session, SQLite for v0), httpx for outbound HTTP (Phase 3 will use it for real), pytest-asyncio for async tests (already configured `asyncio_mode = "auto"`), frozen JSON fixtures (no VCR — keeps Phase 2 simple).

**Out of scope for this phase (called out so it's not forgotten):**
- API endpoints for triggering sync — `/api/connectors/...` lands in Phase 3.
- OAuth UI flow — Phase 3.
- Incremental sync — `sync_full` only. `sync_incremental` is declared on the ABC but raises `NotImplementedError` for now.
- Real credential encryption — column is named `auth_blob_encrypted` (per `docs/architecture.md §4.1`) but stores plain JSON in demo mode. AES-GCM lands with real OAuth in Phase 3.
- Rate limiting + retries — the interface allows them (per-connector responsibility); real implementation lands when we hit a real API in Phase 3.
- Meta Ads + Shiprocket connectors — Phase 3 once Shopify proves the abstraction.
- SQLite `PRAGMA foreign_keys=ON` — left off for Phase 2 simplicity. All writes are controlled by `RowSink` and the seed function; orphans aren't possible by construction. Add the PRAGMA when we open writes to external callers.

---

## File map

**New files (with one-line responsibility):**

- `apps/api/src/munim/schemas/order.py` — `Order` Pydantic model (canonical normalized shape for an order, source-agnostic).
- `apps/api/src/munim/schemas/tests/__init__.py` — empty package marker.
- `apps/api/src/munim/schemas/tests/test_order.py` — round-trip + validation tests for `Order`.
- `apps/api/src/munim/models/__init__.py` — re-exports the SQLModel tables so `init_db` registers them all by importing this one module.
- `apps/api/src/munim/models/merchant.py` — `Merchant` table.
- `apps/api/src/munim/models/connector_credentials.py` — `ConnectorCredentials` table.
- `apps/api/src/munim/models/record.py` — `Record` table (the universal storage row).
- `apps/api/src/munim/models/run_log.py` — `RunLog` table.
- `apps/api/src/munim/models/tests/__init__.py` — empty.
- `apps/api/src/munim/models/tests/test_tables.py` — create-tables + basic CRUD + unique-constraint tests.
- `apps/api/src/munim/connectors/__init__.py` — empty.
- `apps/api/src/munim/connectors/base.py` — `Credential`, `SyncContext`, `SyncResult`, `RowSink`, `BaseConnector` ABC.
- `apps/api/src/munim/connectors/tests/__init__.py` — empty.
- `apps/api/src/munim/connectors/tests/test_row_sink.py` — `RowSink` upsert/idempotency tests.
- `apps/api/src/munim/connectors/shopify/__init__.py` — empty.
- `apps/api/src/munim/connectors/shopify/client.py` — `ShopifyClient` (demo iterator now; real HTTP in Phase 3).
- `apps/api/src/munim/connectors/shopify/mapper.py` — Shopify order JSON → `Order` Pydantic.
- `apps/api/src/munim/connectors/shopify/connector.py` — `ShopifyConnector` implementing `BaseConnector`.
- `apps/api/src/munim/connectors/shopify/tests/__init__.py` — empty.
- `apps/api/src/munim/connectors/shopify/tests/test_mapper.py` — mapper unit tests (3 frozen orders, one per payment method).
- `apps/api/src/munim/connectors/shopify/tests/test_connector.py` — end-to-end demo-sync integration test.
- `apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json` — frozen Shopify Admin API response (3 orders: COD, prepaid, partial).

**Modified files:**

- `apps/api/src/munim/shared/constants.py` — add enums: `EntityType`, `SourceSystem`, `PaymentMethod`, `CredentialStatus`, `ConnectorName`, `RunLogKind`.
- `apps/api/src/munim/shared/db.py` — make `init_db()` import the model package so `SQLModel.metadata` knows the tables, then seed the default merchant.
- `apps/api/src/munim/schemas/__init__.py` — re-export `Order` for clean imports.
- `apps/api/conftest.py` — add a `session` fixture for tests that need a DB session without going through TestClient.

---

## Task 1 — Constants: add enums for entity types, sources, payments, credential/run state

**Files:**
- Modify: `apps/api/src/munim/shared/constants.py`

- [ ] **Step 1: Replace `constants.py` with the expanded enum set**

```python
"""Cross-module enums.

Per docs/conventions.md §7: NO magic strings in critical comparisons. Status
checks, error codes, payment methods, entity types all live in StrEnums and
get mirrored to the frontend as `as const` unions.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    SYSTEM_UNEXPECTED = "system.unexpected"
    SYSTEM_DATABASE_UNAVAILABLE = "system.database_unavailable"
    VALIDATION_MISSING_FIELD = "validation.missing_field"
    VALIDATION_BAD_FORMAT = "validation.bad_format"
    CONNECTOR_NOT_CONFIGURED = "connector.not_configured"
    CONNECTOR_SYNC_FAILED = "connector.sync_failed"


class EntityType(StrEnum):
    ORDER = "order"
    SHIPMENT = "shipment"
    AD_SPEND = "ad_spend"
    CUSTOMER = "customer"
    PRODUCT = "product"
    PAYMENT = "payment"


class SourceSystem(StrEnum):
    SHOPIFY = "shopify"
    META_ADS = "meta_ads"
    SHIPROCKET = "shiprocket"


class ConnectorName(StrEnum):
    SHOPIFY = "shopify"
    META_ADS = "meta_ads"
    SHIPROCKET = "shiprocket"


class PaymentMethod(StrEnum):
    COD = "cod"
    PREPAID = "prepaid"
    PARTIAL = "partial"


class CredentialStatus(StrEnum):
    CONNECTED = "connected"
    DEMO = "demo"
    ERROR = "error"


class RunLogKind(StrEnum):
    SYNC = "sync"
    CHAT = "chat"
    AGENT = "agent"
```

- [ ] **Step 2: Run lint to confirm the file is clean**

Run (from `apps/api`):
```
uv run ruff check src/munim/shared/constants.py
uv run ruff format --check src/munim/shared/constants.py
```
Expected: `All checks passed!` and no format diffs.

- [ ] **Step 3: Commit**

```
git add apps/api/src/munim/shared/constants.py
git commit -m "feat(constants): add enums for entity/source/payment/credential/run state"
```

---

## Task 2 — `Order` Pydantic entity schema

**Files:**
- Create: `apps/api/src/munim/schemas/order.py`
- Modify: `apps/api/src/munim/schemas/__init__.py`
- Create: `apps/api/src/munim/schemas/tests/__init__.py`
- Create: `apps/api/src/munim/schemas/tests/test_order.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/schemas/tests/__init__.py` as an empty file.

Create `apps/api/src/munim/schemas/tests/test_order.py`:
```python
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from munim.schemas import Order
from munim.shared.constants import PaymentMethod


def _base_order_kwargs() -> dict:
    return {
        "placed_at": datetime(2026, 5, 1, 10, 30, tzinfo=UTC),
        "total_inr": Decimal("1234.50"),
        "currency": "INR",
        "payment_method": PaymentMethod.COD,
        "financial_status": "pending",
        "fulfillment_status": None,
        "pincode": "560001",
        "customer_source_id": "cust_42",
        "utm_campaign": "meta_summer",
        "line_items_count": 2,
    }


def test_order_round_trips_via_json() -> None:
    order = Order(**_base_order_kwargs())
    payload = order.model_dump(mode="json")

    rebuilt = Order.model_validate(payload)
    assert rebuilt == order


def test_order_serialises_decimal_as_string() -> None:
    order = Order(**_base_order_kwargs())
    payload = order.model_dump(mode="json")

    assert payload["total_inr"] == "1234.50"
    assert isinstance(payload["total_inr"], str)


def test_order_rejects_unknown_payment_method() -> None:
    kwargs = _base_order_kwargs()
    kwargs["payment_method"] = "cheque"

    with pytest.raises(ValidationError):
        Order(**kwargs)


def test_order_accepts_pincode_with_leading_zero() -> None:
    kwargs = _base_order_kwargs()
    kwargs["pincode"] = "000123"

    order = Order(**kwargs)
    assert order.pincode == "000123"


def test_order_total_preserves_decimal_precision_through_json_round_trip() -> None:
    # Fails if anyone "fixes" total_inr to float — precision would be lost
    # on round-trip. The whole point of using Decimal for money.
    kwargs = _base_order_kwargs()
    kwargs["total_inr"] = Decimal("9999999.99")

    order = Order(**kwargs)
    rebuilt = Order.model_validate(order.model_dump(mode="json"))
    assert rebuilt.total_inr == Decimal("9999999.99")
```

- [ ] **Step 2: Run tests to confirm they fail with import errors**

Run (from `apps/api`):
```
uv run pytest src/munim/schemas/tests/test_order.py -v
```
Expected: ImportError / ModuleNotFoundError on `from munim.schemas import Order`.

- [ ] **Step 3: Create `Order` model**

Create `apps/api/src/munim/schemas/order.py`:
```python
"""Canonical normalized shape for an order, source-agnostic.

Per docs/architecture.md §4.2: this is the Pydantic model that lives in the
`normalized` JSON column of a `record` row when `entity_type='order'`.
Connectors map their source payload into this shape.

Money is `Decimal`, serialised as a string (per docs/conventions.md §8.1).
Time is timezone-aware UTC (per §8.2). Pincode is a string to preserve
leading zeros.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from munim.shared.constants import PaymentMethod


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placed_at: datetime
    total_inr: Decimal
    currency: str = "INR"
    payment_method: PaymentMethod
    financial_status: str
    fulfillment_status: str | None = None
    pincode: str | None = None
    customer_source_id: str | None = None
    utm_campaign: str | None = None
    line_items_count: int = Field(default=0, ge=0)
```

- [ ] **Step 4: Re-export from `schemas/__init__.py`**

Overwrite `apps/api/src/munim/schemas/__init__.py`:
```python
from munim.schemas.order import Order

__all__ = ["Order"]
```

- [ ] **Step 5: Run tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/schemas/tests/test_order.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Lint + typecheck**

```
uv run ruff check src/munim/schemas
uv run ruff format --check src/munim/schemas
uv run mypy src/munim/schemas
```
Expected: all green.

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/schemas
git commit -m "feat(schemas): add Order Pydantic model (canonical normalized shape)"
```

---

## Task 3 — SQLModel tables + `init_db` seeding the default merchant

**Files:**
- Create: `apps/api/src/munim/models/__init__.py`
- Create: `apps/api/src/munim/models/merchant.py`
- Create: `apps/api/src/munim/models/connector_credentials.py`
- Create: `apps/api/src/munim/models/record.py`
- Create: `apps/api/src/munim/models/run_log.py`
- Create: `apps/api/src/munim/models/tests/__init__.py`
- Create: `apps/api/src/munim/models/tests/test_tables.py`
- Modify: `apps/api/src/munim/shared/db.py`
- Modify: `apps/api/conftest.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/models/tests/__init__.py` as an empty file.

Create `apps/api/src/munim/models/tests/test_tables.py`:
```python
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from munim.models import ConnectorCredentials, Merchant, Record, RunLog
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    EntityType,
    RunLogKind,
    SourceSystem,
)


DEFAULT_MERCHANT_ID = "m_default"


def test_default_merchant_seeded(session: Session) -> None:
    merchant = session.get(Merchant, DEFAULT_MERCHANT_ID)
    assert merchant is not None
    assert merchant.name == "Default Merchant"


def test_record_round_trip(session: Session) -> None:
    record = Record(
        merchant_id=DEFAULT_MERCHANT_ID,
        source_system=SourceSystem.SHOPIFY.value,
        source_id="order_001",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="hash1",
        raw={"id": "order_001", "currency": "INR"},
        normalized={"placed_at": "2026-05-01T10:30:00Z", "total_inr": "1234.50"},
    )
    session.add(record)
    session.commit()

    loaded = session.exec(select(Record).where(Record.source_id == "order_001")).one()
    assert loaded.raw == {"id": "order_001", "currency": "INR"}
    assert loaded.normalized["total_inr"] == "1234.50"


def test_record_natural_key_is_unique(session: Session) -> None:
    common = {
        "merchant_id": DEFAULT_MERCHANT_ID,
        "source_system": SourceSystem.SHOPIFY.value,
        "source_id": "order_dupe",
        "entity_type": EntityType.ORDER.value,
        "fetched_at": datetime.now(UTC),
        "payload_hash": "hash",
        "raw": {},
        "normalized": {},
    }
    session.add(Record(**common))
    session.commit()

    session.add(Record(**common))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_connector_credentials_unique_per_merchant_and_connector(session: Session) -> None:
    session.add(
        ConnectorCredentials(
            merchant_id=DEFAULT_MERCHANT_ID,
            connector=ConnectorName.SHOPIFY.value,
            auth_blob_encrypted='{"status":"demo"}',
            status=CredentialStatus.DEMO.value,
        )
    )
    session.commit()

    session.add(
        ConnectorCredentials(
            merchant_id=DEFAULT_MERCHANT_ID,
            connector=ConnectorName.SHOPIFY.value,
            auth_blob_encrypted='{"status":"demo"}',
            status=CredentialStatus.DEMO.value,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
```

- [ ] **Step 2: Run the tests to confirm they fail with import errors**

Run (from `apps/api`):
```
uv run pytest src/munim/models/tests/test_tables.py -v
```
Expected: ImportError on `from munim.models import ...`.

- [ ] **Step 3: Create the `Merchant` table**

Create `apps/api/src/munim/models/merchant.py`:
```python
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Merchant(SQLModel, table=True):
    __tablename__ = "merchant"

    id: str = Field(primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Create the `ConnectorCredentials` table**

Create `apps/api/src/munim/models/connector_credentials.py`:
```python
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ConnectorCredentials(SQLModel, table=True):
    """One row per (merchant, connector). Holds the credential blob.

    The blob is plain JSON in Phase 2 demo mode (no secrets to protect). When
    Phase 3 wires real OAuth, the blob is encrypted with AES-GCM using a key
    sourced from env (per docs/conventions.md §11) - column name retained.
    """

    __tablename__ = "connector_credentials"
    __table_args__ = (
        UniqueConstraint("merchant_id", "connector", name="uq_credentials_merchant_connector"),
    )

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    connector: str
    auth_blob_encrypted: str
    status: str
    last_sync_at: datetime | None = None
```

- [ ] **Step 5: Create the `Record` table**

Create `apps/api/src/munim/models/record.py`:
```python
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class Record(SQLModel, table=True):
    """The universal storage row. One table for every entity type across every
    source system. See docs/architecture.md §4.1.
    """

    __tablename__ = "record"
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "source_system", "source_id", name="uq_record_natural_key"
        ),
        Index("ix_record_merchant_entity_time", "merchant_id", "entity_type", "fetched_at"),
        Index("ix_record_source", "source_system", "source_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    source_system: str
    source_id: str
    entity_type: str
    fetched_at: datetime
    payload_hash: str
    raw: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    normalized: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
```

- [ ] **Step 6: Create the `RunLog` table**

Create `apps/api/src/munim/models/run_log.py`:
```python
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RunLog(SQLModel, table=True):
    """Append-only audit row for any background activity:
    connector syncs, chat turns, agent runs.
    """

    __tablename__ = "run_log"

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    kind: str
    started_at: datetime
    finished_at: datetime | None = None
    detail_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
```

- [ ] **Step 7: Create the `models/__init__.py` re-export**

Create `apps/api/src/munim/models/__init__.py`:
```python
"""SQLModel tables for the universal schema.

Importing this module registers every table on `SQLModel.metadata` so
`init_db()` creates them. Keep the imports here when adding a new table.
"""

from munim.models.connector_credentials import ConnectorCredentials
from munim.models.merchant import Merchant
from munim.models.record import Record
from munim.models.run_log import RunLog

__all__ = [
    "ConnectorCredentials",
    "Merchant",
    "Record",
    "RunLog",
]
```

- [ ] **Step 8: Wire `init_db()` to import models and seed the default merchant**

Replace `apps/api/src/munim/shared/db.py`:
```python
"""Database engine and session.

Sync SQLite for v0. The migration to Postgres at scale is configuration-level
per docs/architecture.md §10 - SQLModel speaks both, and our application code
already scopes every query by `merchant_id`.

`get_engine()` is cached so tests can clear it after patching DATABASE_URL.
"""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from munim.shared.config import get_settings

DEFAULT_MERCHANT_ID = "m_default"
DEFAULT_MERCHANT_NAME = "Default Merchant"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, **_engine_kwargs(settings.database_url))


def init_db() -> None:
    """Create the universal-schema tables and seed the single-tenant merchant."""
    # Importing the models package registers every table on SQLModel.metadata.
    import munim.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _seed_default_merchant(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session


def _seed_default_merchant(engine: Engine) -> None:
    from munim.models import Merchant

    with Session(engine) as session:
        if session.get(Merchant, DEFAULT_MERCHANT_ID) is not None:
            return
        session.add(Merchant(id=DEFAULT_MERCHANT_ID, name=DEFAULT_MERCHANT_NAME))
        session.commit()


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        _ensure_sqlite_parent_dir(url)
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _ensure_sqlite_parent_dir(url: str) -> None:
    file_prefix = "sqlite:///"
    if not url.startswith(file_prefix):
        return
    path = Path(url[len(file_prefix) :])
    path.parent.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 9: Add `session` fixture to `conftest.py`**

Replace `apps/api/conftest.py`:
```python
"""Shared pytest fixtures for apps/api.

Per docs/conventions.md §11.4: no DB mocking. Each test gets a fresh temp
SQLite file via the autouse `_isolated_sqlite` fixture, so even tests that
build their own FastAPI app pick up an isolated DB without having to opt in.

Windows note: the engine MUST be `.dispose()`d before TemporaryDirectory tries
to remove the file, otherwise the SQLAlchemy connection still holds the file
handle and rmtree raises PermissionError.
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture(autouse=True)
def _isolated_sqlite(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        db_url = f"sqlite:///{db_path.as_posix()}"
        monkeypatch.setenv("DATABASE_URL", db_url)

        from munim.shared.config import get_settings
        from munim.shared.db import get_engine

        get_settings.cache_clear()
        get_engine.cache_clear()
        try:
            yield
        finally:
            get_engine().dispose()
            get_settings.cache_clear()
            get_engine.cache_clear()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Real SQLite session against the autouse temp DB.

    Calls `init_db()` so tables exist and the default merchant is seeded
    before the test sees the session.
    """
    from munim.shared.db import get_engine, init_db

    init_db()
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from munim.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 10: Run the table tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/models/tests/test_tables.py -v
```
Expected: 5 passed.

- [ ] **Step 11: Run the full test suite to make sure nothing regressed**

Run (from `apps/api`):
```
uv run pytest -v
```
Expected: 11 passed (5 new + 6 from Phase 1).

- [ ] **Step 12: Lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```
Expected: all green.

- [ ] **Step 13: Commit**

```
git add apps/api/src/munim/models apps/api/src/munim/shared/db.py apps/api/conftest.py
git commit -m "feat(models): universal 4-table schema + seed default merchant"
```

---

## Task 4 — Connector base types: `Credential`, `SyncContext`, `SyncResult`, `BaseConnector` ABC

**Files:**
- Create: `apps/api/src/munim/connectors/__init__.py`
- Create: `apps/api/src/munim/connectors/base.py`

(This task introduces the type machinery only; the `RowSink` writer lands in Task 5 so its upsert logic can be tested in isolation.)

- [ ] **Step 1: Create the empty package**

Create `apps/api/src/munim/connectors/__init__.py` as an empty file.

- [ ] **Step 2: Write `base.py` with the dataclasses + ABC**

Create `apps/api/src/munim/connectors/base.py`:
```python
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
    row_sink: "RowSink"
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
        raise NotImplementedError(
            f"{self.name.value} does not implement incremental sync yet."
        )


# Forward reference for SyncContext.row_sink — RowSink lands in Task 5.
from munim.connectors._row_sink import RowSink  # noqa: E402, F401  -- placed here to avoid circular import on first read
```

Note on the import at the bottom: SyncContext refers to `"RowSink"` as a string forward reference. The actual `RowSink` class will be imported from `_row_sink.py` (created in Task 5). The bottom import resolves the forward reference at runtime without creating an import cycle.

- [ ] **Step 3: Verify the package imports cleanly (no test yet — Task 5 brings tests)**

Run (from `apps/api`):
```
uv run python -c "from munim.connectors.base import BaseConnector, SyncContext, SyncResult, Credential; print('ok')"
```
Expected: prints `ok`. Will fail with ModuleNotFoundError on `_row_sink` — that's expected; the import is wired in Task 5. **For now, comment out the `from munim.connectors._row_sink import RowSink` line at the bottom of `base.py` and re-run. It should print `ok`.**

- [ ] **Step 4: Lint + typecheck**

```
uv run ruff check src/munim/connectors
uv run ruff format --check src/munim/connectors
uv run mypy src/munim/connectors
```
Expected: all green (with the `_row_sink` import commented out — mypy will accept the string forward reference).

- [ ] **Step 5: Commit**

```
git add apps/api/src/munim/connectors
git commit -m "feat(connectors): add BaseConnector ABC + SyncContext/SyncResult/Credential"
```

---

## Task 5 — `RowSink`: the only writer to `record`

**Files:**
- Create: `apps/api/src/munim/connectors/_row_sink.py`
- Create: `apps/api/src/munim/connectors/tests/__init__.py`
- Create: `apps/api/src/munim/connectors/tests/test_row_sink.py`
- Modify: `apps/api/src/munim/connectors/base.py` (uncomment the RowSink import added in Task 4 Step 2)

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/connectors/tests/__init__.py` as an empty file.

Create `apps/api/src/munim/connectors/tests/test_row_sink.py`:
```python
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink, _hash_payload
from munim.models import Record
from munim.schemas import Order
from munim.shared.constants import EntityType, PaymentMethod, SourceSystem

DEFAULT_MERCHANT_ID = "m_default"


def _make_order(total: str = "1234.50") -> Order:
    return Order(
        placed_at=datetime(2026, 5, 1, 10, 30, tzinfo=UTC),
        total_inr=Decimal(total),
        currency="INR",
        payment_method=PaymentMethod.COD,
        financial_status="pending",
        pincode="560001",
        customer_source_id="cust_42",
        line_items_count=2,
    )


def test_row_sink_inserts_a_new_row(session: Session) -> None:
    sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY)
    raw = {"id": "order_001", "total": "1234.50"}

    record, changed = sink.upsert(
        source_id="order_001",
        entity_type=EntityType.ORDER,
        raw=raw,
        normalized=_make_order(),
    )
    session.commit()

    assert changed is True
    assert record.merchant_id == DEFAULT_MERCHANT_ID
    assert record.source_system == SourceSystem.SHOPIFY.value
    assert record.source_id == "order_001"
    assert record.entity_type == EntityType.ORDER.value
    assert record.payload_hash != ""
    assert record.raw == raw
    assert record.normalized["total_inr"] == "1234.50"


def test_row_sink_no_op_when_payload_hash_matches(session: Session) -> None:
    sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY)
    raw = {"id": "order_002", "total": "1000.00"}
    order = _make_order("1000.00")

    sink.upsert(source_id="order_002", entity_type=EntityType.ORDER, raw=raw, normalized=order)
    session.commit()

    record_again, changed_again = sink.upsert(
        source_id="order_002", entity_type=EntityType.ORDER, raw=raw, normalized=order
    )
    session.commit()

    assert changed_again is False
    rows = session.exec(select(Record).where(Record.source_id == "order_002")).all()
    assert len(rows) == 1


def test_row_sink_updates_when_payload_changes(session: Session) -> None:
    sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY)
    first_raw = {"id": "order_003", "total": "500.00"}
    second_raw = {"id": "order_003", "total": "600.00"}

    sink.upsert(
        source_id="order_003",
        entity_type=EntityType.ORDER,
        raw=first_raw,
        normalized=_make_order("500.00"),
    )
    session.commit()

    record, changed = sink.upsert(
        source_id="order_003",
        entity_type=EntityType.ORDER,
        raw=second_raw,
        normalized=_make_order("600.00"),
    )
    session.commit()

    assert changed is True
    assert record.raw == second_raw
    assert record.normalized["total_inr"] == "600.00"
    rows = session.exec(select(Record).where(Record.source_id == "order_003")).all()
    assert len(rows) == 1


def test_row_sink_separates_different_source_systems(session: Session) -> None:
    shopify_sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY)
    meta_sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.META_ADS)
    raw = {"id": "shared_id", "total": "100.00"}

    shopify_sink.upsert(
        source_id="shared_id",
        entity_type=EntityType.ORDER,
        raw=raw,
        normalized=_make_order("100.00"),
    )
    meta_sink.upsert(
        source_id="shared_id",
        entity_type=EntityType.AD_SPEND,
        raw=raw,
        normalized=_make_order("100.00"),
    )
    session.commit()

    rows = session.exec(select(Record).where(Record.source_id == "shared_id")).all()
    assert len(rows) == 2


def test_row_sink_hash_is_canonical_across_key_order() -> None:
    # If this fails, two semantically-identical payloads received in different
    # field order would produce different hashes -> sync would re-write rows
    # forever, losing idempotency. The canonical-JSON guarantee is the whole
    # mechanism behind upsert no-op.
    same_a = {"a": 1, "b": 2, "c": [1, 2, 3]}
    same_b = {"c": [1, 2, 3], "b": 2, "a": 1}
    assert _hash_payload(same_a) == _hash_payload(same_b)


def test_row_sink_preserves_raw_payload_verbatim(session: Session) -> None:
    # Provenance test: the scored axis in the brief is "every numerical claim
    # carries a citation back to the source rows." If RowSink mutates the raw
    # payload (e.g., re-serialising and losing field order, dropping nulls,
    # coercing numbers), citations would point at a fabricated payload, not
    # the source. This locks the invariant that `raw` is byte-equal to the
    # input dict on round-trip.
    sink = RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY)
    quirky_raw = {
        "id": "order_quirk",
        "currency": "INR",
        "discount": None,
        "nested": {"a": 1, "b": [None, 2.5, "leading_zero_zip"]},
        "trailing_zero_amount": "10.50",
    }

    sink.upsert(
        source_id="order_quirk",
        entity_type=EntityType.ORDER,
        raw=quirky_raw,
        normalized=_make_order(),
    )
    session.commit()

    loaded = session.exec(
        select(Record).where(Record.source_id == "order_quirk")
    ).one()
    assert loaded.raw == quirky_raw
```

- [ ] **Step 2: Run tests to confirm they fail with ImportError**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/tests/test_row_sink.py -v
```
Expected: ImportError on `from munim.connectors._row_sink import RowSink`.

- [ ] **Step 3: Implement `RowSink`**

Create `apps/api/src/munim/connectors/_row_sink.py`:
```python
"""The only thing that writes to the `record` table.

Connectors hand `RowSink.upsert(...)` a normalized Pydantic entity + the raw
source payload; the sink stamps provenance (merchant_id, source_system,
fetched_at, payload_hash) and upserts on the natural key
`(merchant_id, source_system, source_id)`.

`commit()` is the CALLER's responsibility - the sink uses `session.add` so a
batch of upserts can be wrapped in one transaction.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session, select

from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


class RowSink:
    def __init__(
        self,
        session: Session,
        merchant_id: str,
        source_system: SourceSystem,
    ) -> None:
        self._session = session
        self._merchant_id = merchant_id
        self._source_system = source_system

    def upsert(
        self,
        *,
        source_id: str,
        entity_type: EntityType,
        raw: dict[str, Any],
        normalized: BaseModel,
    ) -> tuple[Record, bool]:
        """Insert or update one row. Returns (record, was_changed).

        was_changed is True if the row was inserted or its payload_hash
        differed from the existing row; False if the existing row matched
        byte-for-byte and no update was needed.
        """
        payload_hash = _hash_payload(raw)
        normalized_json = normalized.model_dump(mode="json")

        existing = self._session.exec(
            select(Record).where(
                Record.merchant_id == self._merchant_id,
                Record.source_system == self._source_system.value,
                Record.source_id == source_id,
            )
        ).first()

        now = datetime.now(UTC)

        if existing is None:
            record = Record(
                merchant_id=self._merchant_id,
                source_system=self._source_system.value,
                source_id=source_id,
                entity_type=entity_type.value,
                fetched_at=now,
                payload_hash=payload_hash,
                raw=raw,
                normalized=normalized_json,
            )
            self._session.add(record)
            return record, True

        if existing.payload_hash == payload_hash:
            return existing, False

        existing.fetched_at = now
        existing.payload_hash = payload_hash
        existing.raw = raw
        existing.normalized = normalized_json
        self._session.add(existing)
        return existing, True


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Re-enable the import at the bottom of `base.py`**

Open `apps/api/src/munim/connectors/base.py`. Uncomment the line at the bottom so it reads:

```python
from munim.connectors._row_sink import RowSink  # noqa: E402, F401
```

- [ ] **Step 5: Run RowSink tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/tests/test_row_sink.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Run full suite**

Run (from `apps/api`):
```
uv run pytest -v
```
Expected: 15 passed (4 new + 11 from earlier).

- [ ] **Step 7: Lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```
Expected: all green.

- [ ] **Step 8: Commit**

```
git add apps/api/src/munim/connectors
git commit -m "feat(connectors): add RowSink — the only writer to the record table"
```

---

## Task 6 — Shopify demo fixture

**Files:**
- Create: `apps/api/src/munim/connectors/shopify/__init__.py`
- Create: `apps/api/src/munim/connectors/shopify/tests/__init__.py`
- Create: `apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json`

- [ ] **Step 1: Create empty package files**

Create `apps/api/src/munim/connectors/shopify/__init__.py` as empty.
Create `apps/api/src/munim/connectors/shopify/tests/__init__.py` as empty.

- [ ] **Step 2: Create the frozen Shopify Admin API response**

Create `apps/api/src/munim/connectors/shopify/tests/fixtures/orders.json`. This is a trimmed but realistic shape of `GET /admin/api/2025-04/orders.json` for three orders covering all three payment methods (COD, prepaid, partial):

```json
{
  "orders": [
    {
      "id": 5510000000001,
      "name": "#1001",
      "created_at": "2026-05-10T09:15:32+05:30",
      "updated_at": "2026-05-10T09:15:32+05:30",
      "currency": "INR",
      "current_total_price": "1249.00",
      "financial_status": "pending",
      "fulfillment_status": null,
      "payment_gateway_names": ["cash_on_delivery"],
      "source_name": "meta_summer_2026",
      "customer": {
        "id": 7700000000001,
        "email": "a@example.in",
        "phone": "+919900000001"
      },
      "shipping_address": {
        "zip": "560001",
        "city": "Bengaluru",
        "country_code": "IN"
      },
      "line_items": [
        {"id": 1, "name": "T-Shirt", "quantity": 1, "price": "699.00"},
        {"id": 2, "name": "Mug", "quantity": 1, "price": "550.00"}
      ]
    },
    {
      "id": 5510000000002,
      "name": "#1002",
      "created_at": "2026-05-10T14:02:11+05:30",
      "updated_at": "2026-05-10T14:02:11+05:30",
      "currency": "INR",
      "current_total_price": "2199.00",
      "financial_status": "paid",
      "fulfillment_status": "fulfilled",
      "payment_gateway_names": ["razorpay"],
      "source_name": "google_search",
      "customer": {
        "id": 7700000000002,
        "email": "b@example.in",
        "phone": "+919900000002"
      },
      "shipping_address": {
        "zip": "110001",
        "city": "New Delhi",
        "country_code": "IN"
      },
      "line_items": [
        {"id": 3, "name": "Hoodie", "quantity": 1, "price": "2199.00"}
      ]
    },
    {
      "id": 5510000000003,
      "name": "#1003",
      "created_at": "2026-05-11T08:45:00+05:30",
      "updated_at": "2026-05-11T08:45:00+05:30",
      "currency": "INR",
      "current_total_price": "850.00",
      "financial_status": "partially_paid",
      "fulfillment_status": null,
      "payment_gateway_names": ["razorpay", "manual"],
      "source_name": "meta_evergreen",
      "customer": {
        "id": 7700000000003,
        "email": "c@example.in",
        "phone": "+919900000003"
      },
      "shipping_address": {
        "zip": "000123",
        "city": "Unusual Pincode City",
        "country_code": "IN"
      },
      "line_items": [
        {"id": 4, "name": "Cap", "quantity": 2, "price": "425.00"}
      ]
    }
  ]
}
```

- [ ] **Step 3: Commit the fixture so subsequent tasks can use it**

```
git add apps/api/src/munim/connectors/shopify/__init__.py apps/api/src/munim/connectors/shopify/tests
git commit -m "test(shopify): add frozen orders.json fixture (COD + prepaid + partial)"
```

---

## Task 7 — `ShopifyClient` (demo iterator)

**Files:**
- Create: `apps/api/src/munim/connectors/shopify/client.py`
- Create: `apps/api/src/munim/connectors/shopify/tests/test_client.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/connectors/shopify/tests/test_client.py`:
```python
from pathlib import Path

import httpx

from munim.connectors.base import Credential
from munim.connectors.shopify.client import ShopifyClient
from munim.shared.constants import ConnectorName

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id="m_default",
        connector=ConnectorName.SHOPIFY,
        blob={"status": "demo", "fixture_path": str(FIXTURE_PATH)},
    )


async def test_iter_orders_yields_every_fixture_order_in_source_order() -> None:
    # Contract: the client must yield ALL orders from the fixture, preserving
    # the source order. A drop, dedupe, or reorder here would silently swallow
    # data downstream — the connector's sync would just count the survivors
    # and report "success" with the wrong count.
    client = ShopifyClient(_demo_credential(), httpx.AsyncClient())
    try:
        seen_ids = [order["id"] async for order in client.iter_orders()]
    finally:
        await client.aclose()
    assert seen_ids == [5510000000001, 5510000000002, 5510000000003]
```

- [ ] **Step 2: Run tests to confirm they fail with ImportError**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_client.py -v
```
Expected: ImportError on `from munim.connectors.shopify.client import ShopifyClient`.

- [ ] **Step 3: Implement the client**

Create `apps/api/src/munim/connectors/shopify/client.py`:
```python
"""HTTP / fixture access to Shopify Admin API.

Phase 2: demo-only. The client reads a frozen JSON fixture pointed to by
`Credential.blob["fixture_path"]` and yields its `orders` array. No network.

Phase 3 will add the real path: build the Admin URL, page through results,
honour rate limits. The interface (`iter_orders`) stays the same so the
connector layer does not change.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from munim.connectors.base import Credential
from munim.shared.constants import CredentialStatus


class ShopifyClient:
    def __init__(self, credential: Credential, http_client: httpx.AsyncClient) -> None:
        self._credential = credential
        self._http_client = http_client

    async def iter_orders(self) -> AsyncIterator[dict[str, Any]]:
        status = self._credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            async for order in self._iter_demo_orders():
                yield order
            return

        raise NotImplementedError(
            "Real Shopify Admin API access lands in Phase 3. Use a demo credential for now."
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def _iter_demo_orders(self) -> AsyncIterator[dict[str, Any]]:
        fixture_path_str = self._credential.blob.get("fixture_path")
        if not fixture_path_str:
            raise ValueError(
                "Demo credential is missing 'fixture_path' — set blob['fixture_path']."
            )

        fixture_path = Path(fixture_path_str)
        with fixture_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        for order in payload["orders"]:
            yield order
```

- [ ] **Step 4: Run tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_client.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Lint + typecheck**

```
uv run ruff check src/munim/connectors/shopify
uv run ruff format --check src/munim/connectors/shopify
uv run mypy src/munim/connectors/shopify
```
Expected: all green.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/connectors/shopify
git commit -m "feat(shopify): add ShopifyClient with demo fixture iterator"
```

---

## Task 8 — Shopify mapper (raw → `Order`)

**Files:**
- Create: `apps/api/src/munim/connectors/shopify/mapper.py`
- Create: `apps/api/src/munim/connectors/shopify/tests/test_mapper.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/connectors/shopify/tests/test_mapper.py`:
```python
import json
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.shared.constants import PaymentMethod

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"


@pytest.fixture(scope="module")
def fixture_orders() -> list[dict]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)["orders"]


def test_maps_cod_order_to_decimal_total_inr(fixture_orders: list[dict]) -> None:
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)

    assert order.total_inr == Decimal("1249.00")
    assert isinstance(order.total_inr, Decimal)
    assert order.payment_method is PaymentMethod.COD
    assert order.currency == "INR"


def test_maps_placed_at_to_utc(fixture_orders: list[dict]) -> None:
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)

    # Shopify sends +05:30; we store UTC.
    assert order.placed_at == datetime(2026, 5, 10, 3, 45, 32, tzinfo=UTC)
    assert order.placed_at.tzinfo is not None


def test_maps_prepaid_order(fixture_orders: list[dict]) -> None:
    prepaid_order = next(o for o in fixture_orders if o["id"] == 5510000000002)
    order = map_shopify_order_to_normalized(prepaid_order)

    assert order.payment_method is PaymentMethod.PREPAID
    assert order.total_inr == Decimal("2199.00")
    assert order.fulfillment_status == "fulfilled"


def test_maps_partial_order_and_preserves_leading_zero_pincode(
    fixture_orders: list[dict],
) -> None:
    partial_order = next(o for o in fixture_orders if o["id"] == 5510000000003)
    order = map_shopify_order_to_normalized(partial_order)

    assert order.payment_method is PaymentMethod.PARTIAL
    assert order.pincode == "000123"


def test_customer_source_id_is_string_even_when_shopify_returns_int(
    fixture_orders: list[dict],
) -> None:
    # Real bug class: Shopify sends customer.id as a JSON number. If we don't
    # explicitly stringify, the typed schema would fail or — worse — store an
    # int in a `str | None` field via Python's duck-typing and break joins.
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)
    assert order.customer_source_id == "7700000000001"


def test_mapper_handles_missing_customer_for_guest_checkout() -> None:
    # Real Shopify edge case: guest checkouts have no customer object. The
    # connector must NOT crash on this — it has to record the order with
    # customer_source_id=None and continue. If we ever lose this branch the
    # sync would die mid-batch on a real store.
    guest_raw = {
        "id": 5510000000099,
        "created_at": "2026-05-12T11:00:00+05:30",
        "currency": "INR",
        "current_total_price": "499.00",
        "financial_status": "paid",
        "fulfillment_status": None,
        "payment_gateway_names": ["razorpay"],
        "customer": None,
        "shipping_address": {"zip": "560002", "city": "Bengaluru", "country_code": "IN"},
        "line_items": [{"id": 99, "name": "Sticker", "quantity": 1, "price": "499.00"}],
    }

    order = map_shopify_order_to_normalized(guest_raw)
    assert order.customer_source_id is None
    assert order.payment_method is PaymentMethod.PREPAID


def test_mapper_preserves_non_inr_currency_instead_of_defaulting() -> None:
    # The Order schema defaults currency="INR" if absent. The mapper must
    # NOT silently use that default when the source actually sends a value —
    # that would mask a multi-currency bug at the worst possible moment.
    usd_raw = {
        "id": 5510000000200,
        "created_at": "2026-05-12T12:00:00+05:30",
        "currency": "USD",
        "current_total_price": "29.99",
        "financial_status": "paid",
        "fulfillment_status": None,
        "payment_gateway_names": ["stripe"],
        "customer": {"id": 12345, "email": "x@example.com"},
        "shipping_address": {"zip": "94110", "city": "SF", "country_code": "US"},
        "line_items": [],
    }

    order = map_shopify_order_to_normalized(usd_raw)
    assert order.currency == "USD"


def test_mapper_raises_on_missing_required_field() -> None:
    # Per docs/conventions.md §10: no silent fallbacks. A malformed source
    # payload must raise so the sync fails loudly, not silently skip rows
    # while reporting "success".
    malformed = {
        "id": 5510000000300,
        # 'created_at' missing — a real Shopify response would never omit
        # this, so its absence is a real signal of upstream corruption.
        "currency": "INR",
        "current_total_price": "100.00",
        "financial_status": "paid",
        "payment_gateway_names": ["razorpay"],
    }

    with pytest.raises(KeyError):
        map_shopify_order_to_normalized(malformed)
```

- [ ] **Step 2: Run tests to confirm they fail with ImportError**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_mapper.py -v
```
Expected: ImportError on `from munim.connectors.shopify.mapper import map_shopify_order_to_normalized`.

- [ ] **Step 3: Implement the mapper**

Create `apps/api/src/munim/connectors/shopify/mapper.py`:
```python
"""Map a Shopify Admin API order payload to the canonical `Order` Pydantic.

This is the only place that knows the shape of Shopify's response. The rest
of the system reads from `Order`.

A malformed order (missing required field, unparseable date, etc.) raises;
the caller decides whether to fail the whole sync or skip the row. The
ShopifyConnector currently lets exceptions propagate (no silent fallbacks).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from munim.schemas import Order
from munim.shared.constants import PaymentMethod

_COD_GATEWAYS = {"cash_on_delivery", "cod"}


def map_shopify_order_to_normalized(raw: dict[str, Any]) -> Order:
    return Order(
        placed_at=_parse_iso(raw["created_at"]),
        total_inr=Decimal(raw["current_total_price"]),
        currency=raw.get("currency", "INR"),
        payment_method=_infer_payment_method(raw),
        financial_status=raw["financial_status"],
        fulfillment_status=raw.get("fulfillment_status"),
        pincode=_extract_pincode(raw),
        customer_source_id=_extract_customer_id(raw),
        utm_campaign=raw.get("source_name"),
        line_items_count=len(raw.get("line_items", [])),
    )


def _parse_iso(value: str) -> datetime:
    # Shopify sends "+05:30" style offsets; fromisoformat handles them in 3.11+.
    dt = datetime.fromisoformat(value)
    return dt.astimezone(tz=dt.tzinfo) if dt.tzinfo else dt


def _infer_payment_method(raw: dict[str, Any]) -> PaymentMethod:
    financial_status = raw.get("financial_status", "")
    gateways = [g.lower() for g in raw.get("payment_gateway_names", [])]

    if financial_status == "partially_paid":
        return PaymentMethod.PARTIAL
    if any(g in _COD_GATEWAYS for g in gateways):
        return PaymentMethod.COD
    return PaymentMethod.PREPAID


def _extract_pincode(raw: dict[str, Any]) -> str | None:
    shipping = raw.get("shipping_address") or {}
    zip_value = shipping.get("zip")
    return str(zip_value) if zip_value is not None else None


def _extract_customer_id(raw: dict[str, Any]) -> str | None:
    customer = raw.get("customer") or {}
    cid = customer.get("id")
    return str(cid) if cid is not None else None
```

Note on `_parse_iso`: Shopify timestamps in our fixture are `+05:30`. `datetime.fromisoformat` returns a tz-aware datetime; we keep the awareness. The test asserts the UTC equivalent (`2026-05-10T09:15:32+05:30` → `2026-05-10T03:45:32Z`). Since `astimezone(tz=dt.tzinfo)` is a no-op when `dt.tzinfo == dt.tzinfo`, the function preserves the original offset. The test compares equality where `+05:30` == `UTC` at the same instant — `datetime` equality compares the underlying point in time when both are aware. So `datetime(2026, 5, 10, 9, 15, 32, +05:30) == datetime(2026, 5, 10, 3, 45, 32, UTC)` is `True`.

- [ ] **Step 4: Run tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_mapper.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Lint + typecheck**

```
uv run ruff check src/munim/connectors/shopify
uv run ruff format --check src/munim/connectors/shopify
uv run mypy src/munim/connectors/shopify
```
Expected: all green.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/connectors/shopify/mapper.py apps/api/src/munim/connectors/shopify/tests/test_mapper.py
git commit -m "feat(shopify): map Shopify orders to canonical Order shape"
```

---

## Task 9 — `ShopifyConnector` + end-to-end demo sync integration test

**Files:**
- Create: `apps/api/src/munim/connectors/shopify/connector.py`
- Create: `apps/api/src/munim/connectors/shopify/tests/test_connector.py`

- [ ] **Step 1: Write the failing end-to-end integration test first**

Create `apps/api/src/munim/connectors/shopify/tests/test_connector.py`:
```python
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.shopify.connector import ShopifyConnector
from munim.models import Record
from munim.shared.constants import (
    ConnectorName,
    EntityType,
    PaymentMethod,
    SourceSystem,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"
DEFAULT_MERCHANT_ID = "m_default"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.SHOPIFY,
        blob={"status": "demo", "fixture_path": str(FIXTURE_PATH)},
    )


async def test_shopify_demo_sync_full_writes_three_records(session: Session) -> None:
    connector = ShopifyConnector()
    ctx = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY),
        http_client=httpx.AsyncClient(),
    )
    try:
        result = await connector.sync_full(ctx)
        session.commit()
    finally:
        await ctx.http_client.aclose()

    assert result.rows_upserted == 3
    assert result.rows_skipped == 0
    assert result.errors == []
    assert result.finished_at >= result.started_at

    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == DEFAULT_MERCHANT_ID)
        .where(Record.source_system == SourceSystem.SHOPIFY.value)
        .order_by(Record.source_id)
    ).all()
    assert len(rows) == 3
    assert {r.entity_type for r in rows} == {EntityType.ORDER.value}

    by_source_id = {r.source_id: r for r in rows}
    cod = by_source_id["5510000000001"]
    assert cod.normalized["payment_method"] == PaymentMethod.COD.value
    assert Decimal(cod.normalized["total_inr"]) == Decimal("1249.00")
    assert cod.raw["financial_status"] == "pending"


async def test_shopify_demo_sync_full_is_idempotent(session: Session) -> None:
    connector = ShopifyConnector()
    ctx_a = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY),
        http_client=httpx.AsyncClient(),
    )
    try:
        first = await connector.sync_full(ctx_a)
        session.commit()
    finally:
        await ctx_a.http_client.aclose()

    ctx_b = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY),
        http_client=httpx.AsyncClient(),
    )
    try:
        second = await connector.sync_full(ctx_b)
        session.commit()
    finally:
        await ctx_b.http_client.aclose()

    assert first.rows_upserted == 3
    assert second.rows_upserted == 0
    assert second.rows_skipped == 3

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHOPIFY.value)
    ).all()
    assert len(rows) == 3


async def test_shopify_validate_accepts_demo_and_defers_real_credentials() -> None:
    # Locks the full validate contract: demo passes, real credential is
    # explicitly deferred (NotImplementedError) — not silently treated as
    # valid. The second half of this test catches the bug where a future
    # change to validate() defaults to `return True` and accidentally
    # lets unverified credentials through.
    connector = ShopifyConnector()
    assert await connector.validate(_demo_credential()) is True

    real_cred = Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.SHOPIFY,
        blob={"status": "connected", "access_token": "xxx"},
    )
    with pytest.raises(NotImplementedError):
        await connector.validate(real_cred)


async def test_shopify_sync_preserves_raw_payload_verbatim(session: Session) -> None:
    # End-to-end provenance proof: after a full demo sync, each `record.raw`
    # must equal the exact dict that came out of the fixture. This is the
    # SCORED axis in the brief — "provenance on every row" — verified end
    # to end across mapper + RowSink + DB JSON column.
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        fixture_orders = json.load(handle)["orders"]
    expected_by_id = {str(o["id"]): o for o in fixture_orders}

    connector = ShopifyConnector()
    ctx = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHOPIFY),
        http_client=httpx.AsyncClient(),
    )
    try:
        await connector.sync_full(ctx)
        session.commit()
    finally:
        await ctx.http_client.aclose()

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHOPIFY.value)
    ).all()
    for row in rows:
        assert row.raw == expected_by_id[row.source_id]
```

(Note: the small `_silence_unused_imports` shim avoids a ruff F401 when these stay imported during incremental dev — once the file is final, the imports they protect are used. You can drop the shim if your final test file doesn't need it.)

- [ ] **Step 2: Run the failing tests**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_connector.py -v
```
Expected: ImportError on `from munim.connectors.shopify.connector import ShopifyConnector`.

- [ ] **Step 3: Implement `ShopifyConnector`**

Create `apps/api/src/munim/connectors/shopify/connector.py`:
```python
"""ShopifyConnector — the first concrete implementation of `BaseConnector`.

Phase 2: only `validate` and `sync_full` work, and only against demo
credentials. `authorize_url` / `exchange_code` / real-credential paths raise
NotImplementedError and are completed in Phase 3.
"""

from datetime import UTC, datetime
from typing import ClassVar

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.shopify.client import ShopifyClient
from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType


class ShopifyConnector(BaseConnector):
    name: ClassVar[ConnectorName] = ConnectorName.SHOPIFY

    def authorize_url(self, merchant_id: str) -> str:
        raise NotImplementedError(
            "OAuth UI lands in Phase 3. Use a demo credential for Phase 2."
        )

    async def exchange_code(self, merchant_id: str, code: str) -> Credential:
        raise NotImplementedError(
            "OAuth UI lands in Phase 3. Use a demo credential for Phase 2."
        )

    async def validate(self, credential: Credential) -> bool:
        if credential.blob.get("status") == CredentialStatus.DEMO.value:
            return True
        raise NotImplementedError(
            "Real Shopify credential validation lands in Phase 3."
        )

    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        started_at = datetime.now(UTC)
        client = ShopifyClient(ctx.credential, ctx.http_client)

        rows_upserted = 0
        rows_skipped = 0

        async for raw_order in client.iter_orders():
            order = map_shopify_order_to_normalized(raw_order)
            _, changed = ctx.row_sink.upsert(
                source_id=str(raw_order["id"]),
                entity_type=EntityType.ORDER,
                raw=raw_order,
                normalized=order,
            )
            if changed:
                rows_upserted += 1
            else:
                rows_skipped += 1

        return SyncResult(
            rows_upserted=rows_upserted,
            rows_skipped=rows_skipped,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
```

- [ ] **Step 4: Run the integration tests to confirm they pass**

Run (from `apps/api`):
```
uv run pytest src/munim/connectors/shopify/tests/test_connector.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run the full suite + lint + typecheck**

Run (from `apps/api`):
```
uv run pytest -v
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```
Expected: all green. Total test count should be **26** (6 health + 4 order + 4 tables + 6 row_sink + 1 client + 8 mapper + 3 connector). Counts may shift slightly if a test was renamed or split during implementation — what matters is that no trivial tests slipped in per §13.4.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/connectors/shopify/connector.py apps/api/src/munim/connectors/shopify/tests/test_connector.py
git commit -m "feat(shopify): wire ShopifyConnector + end-to-end demo sync"
```

---

## Task 10 — Update docs (`CHANGELOG.md`, `context.md`) and finalize Phase 2

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `context.md`

- [ ] **Step 1: Add a CHANGELOG entry at the top**

In `CHANGELOG.md`, insert a new section above the Phase 1 entry. Replace `<YYYY-MM-DD>` with the actual date the phase finishes:

```
## <YYYY-MM-DD> — Phase 2: universal schema + Shopify connector (demo mode)

**What changed:** Added the 4 SQLModel tables (`merchant`, `connector_credentials`, `record`, `run_log`) and the canonical `Order` Pydantic shape under `apps/api/src/munim/schemas/`. Added the connector abstraction in `apps/api/src/munim/connectors/base.py`: `Credential`, `SyncContext`, `SyncResult`, `BaseConnector` ABC, and `RowSink` — the only writer to the `record` table, which stamps provenance and upserts on `(merchant_id, source_system, source_id)`. Wired the first concrete connector, `ShopifyConnector`, with a demo iterator that reads a frozen `orders.json` fixture (3 orders covering COD / prepaid / partial). End-to-end integration tests prove the source-API → mapper → RowSink → `record` flow.

**Verified:** all tests pass (24 total). `init_db()` seeds the default merchant and creates every table.

**Files touched:**
- `apps/api/src/munim/schemas/order.py` (+ `__init__.py`, tests).
- `apps/api/src/munim/models/{merchant,connector_credentials,record,run_log}.py` (+ `__init__.py`, tests).
- `apps/api/src/munim/connectors/{base.py,_row_sink.py}` (+ tests).
- `apps/api/src/munim/connectors/shopify/{client,mapper,connector}.py` (+ fixtures, tests).
- `apps/api/src/munim/shared/{constants.py,db.py}` (expanded enums; init_db imports models + seeds merchant).
- `apps/api/conftest.py` (added `session` fixture).

**Reverts cleanly?:** yes — the new `models/` and `connectors/` packages can be deleted entirely; `shared/constants.py` and `shared/db.py` revert to their Phase 1 form.
```

- [ ] **Step 2: Update `context.md`**

In `context.md`, update:
- **Now**: "Phase 2 complete. Universal schema + RowSink + ShopifyConnector demo sync working end-to-end. Next: Phase 3 — API endpoints to trigger the sync + connector management UI."
- **Done**: append a line for Phase 2 dated today.
- **Next**: replace the Phase 2 entry with the Phase 3 description (API endpoints + demo UI + real OAuth scaffold).
- **Problems & solutions**: add any new entries the phase produced (none yet — fill in as they appear during implementation).
- **Decisions**: append any non-obvious decisions made during implementation.
- **AI tool usage**: append one line noting whether implementation was by Claude inline or by a coder subagent.

- [ ] **Step 3: Commit the docs**

```
git add CHANGELOG.md context.md
git commit -m "docs(phase-2): record Phase 2 completion + decisions + paid lessons"
```

- [ ] **Step 4: Final smoke (optional but recommended)**

Boot the api in another shell and confirm tables exist:

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location apps/api
uv run python -c "from munim.shared.db import init_db, get_engine; init_db(); from sqlalchemy import inspect; print(sorted(inspect(get_engine()).get_table_names()))"
```

Expected: `['connector_credentials', 'merchant', 'record', 'run_log']`.

---

## Self-review

(Performed by Claude before handing off the plan.)

**Spec coverage check:**
- Universal schema (4 tables) → Task 3.
- Provenance on every row → built into `RowSink` (Task 5) and the `Record` table's mandatory columns (Task 3).
- `BaseConnector` abstraction with one interface, swappable → Tasks 4 + 5.
- First concrete connector (Shopify) → Tasks 6, 7, 8, 9.
- Source-agnostic normalized entity → `Order` Pydantic (Task 2); enums in Task 1 are also source-agnostic.
- Idempotency on re-run → covered by Task 5 RowSink hash check + Task 9 integration test (`test_shopify_demo_sync_full_is_idempotent`).
- Demo mode without API keys → Tasks 6 (fixture) + 7 (demo client) + 9 (sync against demo).
- `merchant_id` everywhere → all tables include it (Task 3); RowSink scopes by it (Task 5).

**Out-of-scope deliberately deferred (re-listed for transparency):** API endpoints, OAuth UI, real-mode HTTP, AES-GCM credential encryption, incremental sync, rate limiting, Meta + Shiprocket connectors, FK pragma.

**Placeholder scan:** none. Every step has actual code or an exact command.

**Type/name consistency check:**
- `Order` (schemas/order.py) is the canonical entity used by mapper (Task 8), RowSink test (Task 5), and connector test (Task 9). ✓
- `Record` (models/record.py) is the target row used by RowSink (Task 5) and connector test (Task 9). ✓
- `SyncContext` declared in `connectors/base.py` (Task 4) with fields `merchant_id`, `credential`, `row_sink`, `http_client`, `cursor`, `extras` — used in Task 9 with the first four (`cursor`/`extras` left default). ✓
- `RowSink` constructor `(session, merchant_id, source_system)` — used identically in Task 5 tests and Task 9 integration test. ✓
- `ConnectorName.SHOPIFY` enum value `"shopify"` — used in `ShopifyConnector.name`, demo credential blob, and the test assertions. ✓
- `CredentialStatus.DEMO.value == "demo"` — used in the credential blob, the ShopifyClient gate, and the ShopifyConnector.validate gate. ✓
