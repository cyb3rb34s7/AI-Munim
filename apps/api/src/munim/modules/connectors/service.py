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
_API_ROOT = Path(__file__).parents[4]


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
    return [_build_view(session, merchant_id, name) for name in registry.names()]


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
        # At this boundary, anything the connector fails on IS a sync failure.
        # Typed MunimError subclasses propagate as-is so the frontend gets the
        # specific code (e.g., connector.rate_limited later); anything else is
        # rewrapped as connector.sync_failed instead of leaking as
        # system.unexpected. NOT a silent fallback per §10: we re-raise loudly
        # with the original exception chained.
        try:
            result = await connector.sync_full(ctx)
        except MunimError:
            raise
        except Exception as exc:
            raise ConnectorSyncError(
                message=f"Sync failed for connector {name.value!r}: {exc}",
                details={"connector": name.value, "exc_type": type(exc).__name__},
            ) from exc

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


def _build_view(session: Session, merchant_id: str, name: ConnectorName) -> ConnectorView:
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
