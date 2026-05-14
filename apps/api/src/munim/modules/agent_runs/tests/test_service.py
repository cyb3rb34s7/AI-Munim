from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from munim.models import Record
from munim.modules.agent_runs.service import AgentRunFailedError, trigger_agent
from munim.shared.constants import (
    AgentName,
    EntityType,
    PaymentMethod,
    SourceSystem,
)


def test_trigger_agent_wraps_malformed_record_data_in_typed_failure(session: Session) -> None:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id="malformed_cod",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="malformed_h",
        raw={"id": "malformed_cod"},
        normalized={
            "currency": "INR",
            "payment_method": PaymentMethod.COD.value,
            "pincode": "110001",
            "customer_source_id": "cust_y",
        },
    )
    session.add(row)
    session.commit()

    with pytest.raises(AgentRunFailedError) as exc_info:
        trigger_agent(session, "m_default", AgentName.RTO_MITIGATOR)
    assert exc_info.value.code == "agent.run_failed"
    assert exc_info.value.http_status == 500


def test_trigger_agent_naive_timestamp_wrapped_as_typed_failure(session: Session) -> None:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id="naive_cod",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="naive_h",
        raw={"id": "naive_cod"},
        normalized={
            "placed_at": "2026-05-10T23:45:00",
            "total_inr": "1000",
            "currency": "INR",
            "payment_method": PaymentMethod.COD.value,
            "pincode": "110001",
            "customer_source_id": "cust_z",
        },
    )
    session.add(row)
    session.commit()

    with pytest.raises(AgentRunFailedError):
        trigger_agent(session, "m_default", AgentName.RTO_MITIGATOR)
