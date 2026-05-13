from typing import ClassVar

import pytest
from sqlmodel import Session

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.registry import ConnectorRegistry, default_registry
from munim.modules.connectors.service import (
    ConnectorNotConnectedError,
    ConnectorSyncError,
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
    with pytest.raises(ConnectorNotConnectedError) as exc_info:
        await sync_connector(
            session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, default_registry()
        )
    assert exc_info.value.code == "connector.not_connected"


class _RaisingConnector(BaseConnector):
    """Stub connector whose sync_full always raises an untyped exception."""

    name: ClassVar[ConnectorName] = ConnectorName.SHOPIFY

    def authorize_url(self, merchant_id: str) -> str:
        raise NotImplementedError

    async def exchange_code(self, merchant_id: str, code: str) -> Credential:
        raise NotImplementedError

    async def validate(self, credential: Credential) -> bool:
        return True

    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        raise RuntimeError("connector blew up mid-sync")


async def test_sync_wraps_untyped_exception_as_connector_sync_failed(
    session: Session,
) -> None:
    # If a connector raises something untyped (network glitch, mapper bug,
    # KeyError on an unexpected payload), the frontend must see
    # 'connector.sync_failed' — NOT 'system.unexpected'. Without the typed
    # wrap in service.sync_connector, this test fails by raising the bare
    # RuntimeError up to the caller and breaking the error-code contract.
    connect_demo(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY)
    session.commit()

    raising_registry = ConnectorRegistry({ConnectorName.SHOPIFY: _RaisingConnector()})

    with pytest.raises(ConnectorSyncError) as exc_info:
        await sync_connector(session, DEFAULT_MERCHANT_ID, ConnectorName.SHOPIFY, raising_registry)
    assert exc_info.value.code == "connector.sync_failed"
    # `from exc` chaining must be preserved so logs/observability can see
    # the original failure cause.
    assert isinstance(exc_info.value.__cause__, RuntimeError)
