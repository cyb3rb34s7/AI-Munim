import json
from decimal import Decimal
from pathlib import Path
from typing import Any

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

DEFAULT_MERCHANT_ID = "m_default"

_PACKAGE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "orders.json"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.SHOPIFY,
        blob={"status": "demo"},
    )


def _package_fixture_orders() -> list[dict[str, Any]]:
    with _PACKAGE_FIXTURE.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    orders: list[dict[str, Any]] = payload["data"]
    return orders


async def test_shopify_demo_sync_full_writes_package_fixture_rows(session: Session) -> None:
    expected = _package_fixture_orders()
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

    assert result.rows_upserted == len(expected)
    assert result.rows_skipped == 0
    assert result.errors == []
    assert result.finished_at >= result.started_at

    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == DEFAULT_MERCHANT_ID)
        .where(Record.source_system == SourceSystem.SHOPIFY.value)
        .order_by(Record.source_id)
    ).all()
    assert len(rows) == len(expected)
    assert {r.entity_type for r in rows} == {EntityType.ORDER.value}

    by_source_id = {r.source_id: r for r in rows}
    cod_id = str(next(o["id"] for o in expected if o["financial_status"] == "pending"))
    cod = by_source_id[cod_id]
    assert cod.normalized["payment_method"] == PaymentMethod.COD.value
    assert isinstance(Decimal(cod.normalized["total_inr"]), Decimal)


async def test_shopify_demo_sync_full_is_idempotent(session: Session) -> None:
    expected_count = len(_package_fixture_orders())
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

    assert first.rows_upserted == expected_count
    assert second.rows_upserted == 0
    assert second.rows_skipped == expected_count

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHOPIFY.value)
    ).all()
    assert len(rows) == expected_count


async def test_shopify_demo_sync_uses_package_fixture(session: Session) -> None:
    # The demo credential blob carries ONLY {"status": "demo"} now — the
    # client always reads the package fixture, not a blob-supplied path.
    # If a future refactor reintroduces a blob['fixture_path'] requirement
    # this test fails because the empty-blob credential would raise.
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

    expected_ids = {str(o["id"]) for o in _package_fixture_orders()}
    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHOPIFY.value)
    ).all()
    assert {r.source_id for r in rows} == expected_ids
    assert result.rows_upserted == len(expected_ids)


async def test_shopify_validate_accepts_demo_credential() -> None:
    connector = ShopifyConnector()
    assert await connector.validate(_demo_credential()) is True


async def test_shopify_validate_raises_for_unknown_status() -> None:
    # An unrecognised status must not silently return True — that would let
    # unverified credentials through. Phase 4: demo and connected are handled;
    # anything else raises NotImplementedError.
    connector = ShopifyConnector()
    unknown_cred = Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.SHOPIFY,
        blob={"status": "unknown_status"},
    )
    with pytest.raises(NotImplementedError):
        await connector.validate(unknown_cred)


async def test_shopify_sync_preserves_raw_payload_verbatim(session: Session) -> None:
    # End-to-end provenance proof: after a full demo sync, each `record.raw`
    # must equal the exact dict that came out of the fixture. This is the
    # SCORED axis in the brief — "provenance on every row" — verified end
    # to end across mapper + RowSink + DB JSON column.
    expected_by_id = {str(o["id"]): o for o in _package_fixture_orders()}

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
