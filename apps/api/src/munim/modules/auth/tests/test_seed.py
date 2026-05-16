"""Tests for per-merchant demo seeding.

The 96-row count + customer-hash join are the load-bearing claims:
  - 96 rows = 6 Shopify orders + 40 Meta Ads insights + 50 Shiprocket
    shipments, exactly what the brief's demo narrative needs.
  - Same SHA-256(email) for rohan@example.com in Shopify orders and
    Shiprocket shipments — without this, the RTO agent's customer
    signal would always hit the population baseline.
  - Idempotency — re-running seed produces no duplicate rows.
  - Isolation — merchant A's seed produces zero rows visible to B.
"""

from collections.abc import Generator

import pytest
from sqlmodel import Session, select

from munim.models import ConnectorCredentials, Record
from munim.modules.auth.seed import seed_new_merchant
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    EntityType,
    SourceSystem,
)
from munim.shared.db import get_engine, init_db
from munim.shared.utils.customer_hash import compute_customer_source_id


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    init_db()
    with Session(get_engine()) as session:
        yield session


async def test_seed_writes_96_rows_for_new_merchant(db_session: Session) -> None:
    await seed_new_merchant(db_session, "m_seed_test")
    db_session.commit()

    rows = db_session.exec(select(Record).where(Record.merchant_id == "m_seed_test")).all()
    assert len(rows) == 96

    by_source: dict[SourceSystem, int] = dict.fromkeys(
        (SourceSystem.SHOPIFY, SourceSystem.META_ADS, SourceSystem.SHIPROCKET), 0
    )
    for row in rows:
        by_source[SourceSystem(row.source_system)] += 1
    assert by_source[SourceSystem.SHOPIFY] == 6
    assert by_source[SourceSystem.META_ADS] == 40
    assert by_source[SourceSystem.SHIPROCKET] == 50


async def test_seed_writes_demo_credential_for_each_connector(db_session: Session) -> None:
    await seed_new_merchant(db_session, "m_creds_test")
    db_session.commit()

    creds = db_session.exec(
        select(ConnectorCredentials).where(ConnectorCredentials.merchant_id == "m_creds_test")
    ).all()
    by_name = {ConnectorName(c.connector): c for c in creds}
    assert set(by_name) == {ConnectorName.SHOPIFY, ConnectorName.META_ADS, ConnectorName.SHIPROCKET}
    for cred in by_name.values():
        assert cred.status == CredentialStatus.DEMO.value


async def test_seed_is_idempotent_on_second_call(db_session: Session) -> None:
    await seed_new_merchant(db_session, "m_idem_test")
    db_session.commit()
    first_count = len(
        db_session.exec(select(Record).where(Record.merchant_id == "m_idem_test")).all()
    )

    await seed_new_merchant(db_session, "m_idem_test")
    db_session.commit()
    second_count = len(
        db_session.exec(select(Record).where(Record.merchant_id == "m_idem_test")).all()
    )

    assert first_count == 96
    assert second_count == 96


async def test_shopify_seed_customer_hash_matches_shiprocket_for_rohan(
    db_session: Session,
) -> None:
    # The brief's narrative ("Customer A's COD order → convert_to_prepaid")
    # relies on this: the rohan@example.com row in Shopify orders must
    # produce the same customer_source_id as the rohan@example.com row
    # in the Shiprocket shipments fixture, so the agent's customer_rto_rate
    # signal sees the 3/5 RTO history.
    await seed_new_merchant(db_session, "m_join_test")
    db_session.commit()

    expected_hash = compute_customer_source_id("rohan@example.com", "+919900000005")

    shopify_rohan_rows = [
        row
        for row in db_session.exec(
            select(Record)
            .where(Record.merchant_id == "m_join_test")
            .where(Record.source_system == SourceSystem.SHOPIFY.value)
            .where(Record.entity_type == EntityType.ORDER.value)
        ).all()
        if row.normalized.get("customer_source_id") == expected_hash
    ]
    assert len(shopify_rohan_rows) == 2

    shiprocket_rohan_rows = [
        row
        for row in db_session.exec(
            select(Record)
            .where(Record.merchant_id == "m_join_test")
            .where(Record.source_system == SourceSystem.SHIPROCKET.value)
            .where(Record.entity_type == EntityType.SHIPMENT.value)
        ).all()
        if row.normalized.get("customer_source_id") == expected_hash
    ]
    assert len(shiprocket_rohan_rows) >= 3


async def test_seed_is_isolated_between_merchants(db_session: Session) -> None:
    await seed_new_merchant(db_session, "m_iso_a")
    await seed_new_merchant(db_session, "m_iso_b")
    db_session.commit()

    a_rows = db_session.exec(select(Record).where(Record.merchant_id == "m_iso_a")).all()
    b_rows = db_session.exec(select(Record).where(Record.merchant_id == "m_iso_b")).all()
    assert len(a_rows) == 96
    assert len(b_rows) == 96

    # Spot-check natural-key behaviour: same source_id pair belongs to two
    # different merchant rows, never the same physical record id.
    a_first = a_rows[0]
    b_match = next(
        (
            row
            for row in b_rows
            if row.source_system == a_first.source_system and row.source_id == a_first.source_id
        ),
        None,
    )
    assert b_match is not None
    assert a_first.id != b_match.id
    assert a_first.merchant_id != b_match.merchant_id
