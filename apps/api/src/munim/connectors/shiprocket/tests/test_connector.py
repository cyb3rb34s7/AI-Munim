import httpx
from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.shiprocket.connector import ShiprocketConnector
from munim.models import Record
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    EntityType,
    FulfillmentStatus,
    SourceSystem,
)
from munim.shared.utils.customer_hash import compute_customer_source_id

DEFAULT_MERCHANT_ID = "m_default"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.SHIPROCKET,
        blob={"status": CredentialStatus.DEMO.value},
    )


async def _run_sync(session: Session) -> tuple[int, int]:
    connector = ShiprocketConnector()
    ctx = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.SHIPROCKET),
        http_client=httpx.AsyncClient(),
    )
    try:
        result = await connector.sync_full(ctx)
        session.commit()
    finally:
        await ctx.http_client.aclose()
    return result.rows_upserted, result.rows_skipped


async def test_shiprocket_demo_sync_writes_fifty_shipment_rows(session: Session) -> None:
    upserted, _ = await _run_sync(session)
    assert upserted == 50

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHIPROCKET.value)
    ).all()
    assert len(rows) == 50
    assert {r.entity_type for r in rows} == {EntityType.SHIPMENT.value}


async def test_shiprocket_sync_is_idempotent_on_re_run(session: Session) -> None:
    first, _ = await _run_sync(session)
    second_upserted, second_skipped = await _run_sync(session)
    assert first == 50
    assert second_upserted == 0
    assert second_skipped == 50


async def test_customer_a_has_three_rto_two_delivered(session: Session) -> None:
    # Locks the demo narrative: rohan@example.com is the high-RTO customer the
    # RTO agent's customer_rto_rate must catch. If a future fixture edit breaks
    # this distribution, the agent demo silently misfires.
    await _run_sync(session)
    customer_a_hash = compute_customer_source_id("rohan@example.com", None)

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHIPROCKET.value)
    ).all()
    customer_rows = [r for r in rows if r.normalized.get("customer_source_id") == customer_a_hash]
    assert len(customer_rows) == 5
    rto = [
        r
        for r in customer_rows
        if r.normalized.get("fulfillment_status") == FulfillmentStatus.RTO.value
    ]
    fulfilled = [
        r
        for r in customer_rows
        if r.normalized.get("fulfillment_status") == FulfillmentStatus.FULFILLED.value
    ]
    assert len(rto) == 3
    assert len(fulfilled) == 2


async def test_customer_b_has_clean_record(session: Session) -> None:
    await _run_sync(session)
    customer_b_hash = compute_customer_source_id("priya@example.com", None)

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHIPROCKET.value)
    ).all()
    customer_rows = [r for r in rows if r.normalized.get("customer_source_id") == customer_b_hash]
    assert len(customer_rows) == 5
    assert all(
        r.normalized.get("fulfillment_status") == FulfillmentStatus.FULFILLED.value
        for r in customer_rows
    )


async def test_customer_c_has_one_rto_four_delivered(session: Session) -> None:
    await _run_sync(session)
    customer_c_hash = compute_customer_source_id("amit@example.com", None)

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.SHIPROCKET.value)
    ).all()
    customer_rows = [r for r in rows if r.normalized.get("customer_source_id") == customer_c_hash]
    assert len(customer_rows) == 5
    rto = [
        r
        for r in customer_rows
        if r.normalized.get("fulfillment_status") == FulfillmentStatus.RTO.value
    ]
    fulfilled = [
        r
        for r in customer_rows
        if r.normalized.get("fulfillment_status") == FulfillmentStatus.FULFILLED.value
    ]
    assert len(rto) == 1
    assert len(fulfilled) == 4
