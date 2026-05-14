from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from munim.agents.rto_mitigator.signals import (
    customer_rto_rate,
    order_value_bucket,
    pincode_risk,
    time_of_order_risk,
)
from munim.models import Record
from munim.shared.constants import (
    EntityType,
    FulfillmentStatus,
    PaymentMethod,
    SourceSystem,
)


def _seed_order(
    session: Session,
    *,
    source_id: str,
    customer_id: str,
    pincode: str,
    payment_method: PaymentMethod,
    total_inr: str,
    placed_at: str = "2026-05-10T03:45:32Z",
    fulfillment_status: str | None = None,
) -> Record:
    normalized: dict[str, str | None] = {
        "placed_at": placed_at,
        "total_inr": total_inr,
        "currency": "INR",
        "payment_method": payment_method.value,
        "financial_status": "pending",
        "pincode": pincode,
        "customer_source_id": customer_id,
    }
    if fulfillment_status is not None:
        normalized["fulfillment_status"] = fulfillment_status
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized=normalized,
    )
    session.add(row)
    session.flush()
    return row


def test_order_value_bucket_low_value_returns_low_score() -> None:
    result = order_value_bucket(Decimal("500"))
    assert 0.0 <= result.score < 0.3
    assert result.diagnostic["bucket"] == "low"


def test_order_value_bucket_high_value_returns_high_score() -> None:
    result = order_value_bucket(Decimal("8000"))
    assert result.score >= 0.7
    assert result.diagnostic["bucket"] == "high"


def test_pincode_risk_known_high_risk_pincode_returns_high_score() -> None:
    result = pincode_risk("110001")
    assert result.score >= 0.5
    assert result.diagnostic["pincode"] == "110001"
    assert result.diagnostic["in_high_risk_list"] is True


def test_pincode_risk_unknown_pincode_returns_baseline() -> None:
    result = pincode_risk("999999")
    assert 0.0 <= result.score <= 0.4
    assert result.diagnostic["in_high_risk_list"] is False


def test_pincode_risk_missing_pincode_returns_baseline_with_diagnostic() -> None:
    result = pincode_risk(None)
    assert result.score == 0.2
    assert result.diagnostic["pincode"] is None


def test_time_of_order_risk_ist_late_night_returns_high_score() -> None:
    result = time_of_order_risk("2026-05-10T23:45:00+05:30")
    assert result.score >= 0.6
    assert result.diagnostic["hour_band"] == "late_night"


def test_time_of_order_risk_utc_input_converts_to_ist_late_night() -> None:
    result = time_of_order_risk("2026-05-10T18:15:00Z")
    assert result.score >= 0.6
    assert result.diagnostic["hour_band"] == "late_night"
    assert result.diagnostic["hour_ist"] == 23


def test_time_of_order_risk_business_hours_returns_low_score() -> None:
    result = time_of_order_risk("2026-05-10T14:30:00+05:30")
    assert result.score <= 0.3
    assert result.diagnostic["hour_band"] == "business_hours"


def test_time_of_order_risk_naive_datetime_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="timezone"):
        time_of_order_risk("2026-05-10T23:45:00")


def test_customer_rto_rate_no_history_returns_population_baseline(session: Session) -> None:
    result = customer_rto_rate(session, "m_default", "new_customer_x")
    assert result.score == 0.2
    assert result.diagnostic["history_count"] == 0
    assert result.diagnostic["confident"] is False


def test_customer_rto_rate_missing_customer_id_returns_baseline_with_diagnostic(
    session: Session,
) -> None:
    result = customer_rto_rate(session, "m_default", None)
    assert result.score == 0.2
    assert result.diagnostic["customer_id_missing"] is True
    assert result.diagnostic["confident"] is False


def test_customer_rto_rate_with_history_uses_observed_rate(session: Session) -> None:
    for i in range(5):
        _seed_order(
            session,
            source_id=f"hist_{i}",
            customer_id="customer_x",
            pincode="560001",
            payment_method=PaymentMethod.COD,
            total_inr="1000",
            fulfillment_status=FulfillmentStatus.RTO.value if i < 2 else None,
        )
    session.commit()

    result = customer_rto_rate(session, "m_default", "customer_x")
    assert result.diagnostic["history_count"] == 5
    assert result.diagnostic["rto_count"] == 2
    assert result.diagnostic["confident"] is True
