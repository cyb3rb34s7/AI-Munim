from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from munim.models import ConnectorCredentials, Record, RunLog
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    EntityType,
    RunLogKind,
    SourceSystem,
)

DEFAULT_MERCHANT_ID = "m_default"


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


def test_run_log_import_ok(session: Session) -> None:
    # Verify RunLog and RunLogKind are importable and usable (import smoke test).
    run_log = RunLog(
        merchant_id=DEFAULT_MERCHANT_ID,
        kind=RunLogKind.SYNC.value,
        started_at=datetime.now(UTC),
        detail_json={"rows": 3},
    )
    session.add(run_log)
    session.commit()
    assert run_log.id is not None
