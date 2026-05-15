from datetime import UTC, datetime
from decimal import Decimal

import pytest

from munim.connectors.shiprocket.mapper import (
    MissingCustomerIdentityError,
    UnknownShipmentStatusError,
    compute_customer_source_id,
    map_shiprocket_shipment,
)
from munim.shared.constants import FulfillmentStatus


def _base_row() -> dict[str, object]:
    return {
        "id": 12345001,
        "channel_order_id": "2001",
        "customer_email": "rohan@example.com",
        "customer_phone": "+919900000005",
        "status": "DELIVERED",
        "awb_code": "SR9876543210",
        "courier_name": "Delhivery Surface",
        "total": "1500.00",
        "created_at": "2026-04-15 10:30:00",
        "shipping_address": {"pincode": "110001"},
    }


@pytest.mark.parametrize(
    "raw_status,expected",
    [
        ("DELIVERED", FulfillmentStatus.FULFILLED),
        ("RTO", FulfillmentStatus.RTO),
        ("RTO INITIATED", FulfillmentStatus.RTO),
        ("IN-TRANSIT", FulfillmentStatus.IN_TRANSIT),
        ("PICKUP SCHEDULED", FulfillmentStatus.PENDING),
        ("CANCELED", FulfillmentStatus.CANCELLED),
        ("CANCELLED", FulfillmentStatus.CANCELLED),
    ],
)
def test_status_map_covers_every_known_shiprocket_status(
    raw_status: str, expected: FulfillmentStatus
) -> None:
    row = _base_row()
    row["status"] = raw_status
    result = map_shiprocket_shipment(row)
    assert result.fulfillment_status is expected


def test_unknown_status_raises_typed_error_not_silent_bucket() -> None:
    row = _base_row()
    row["status"] = "MOON_BOUND"
    with pytest.raises(UnknownShipmentStatusError) as exc_info:
        map_shiprocket_shipment(row)
    assert exc_info.value.code == "validation.bad_format"


def test_ist_naive_created_at_converts_to_utc() -> None:
    row = _base_row()
    row["created_at"] = "2026-04-15 10:30:00"
    result = map_shiprocket_shipment(row)

    assert result.placed_at.tzinfo is UTC
    # 10:30 IST is 05:00 UTC (UTC = IST - 5:30)
    assert result.placed_at == datetime(2026, 4, 15, 5, 0, 0, tzinfo=UTC)


def test_already_timezone_aware_created_at_raises_to_lock_contract() -> None:
    row = _base_row()
    row["created_at"] = "2026-04-15T10:30:00+05:30"
    with pytest.raises(ValueError, match="IST-naive"):
        map_shiprocket_shipment(row)


def test_customer_hash_prefers_email_over_phone() -> None:
    email_hash = compute_customer_source_id("rohan@example.com", "+919900000005")
    phone_hash = compute_customer_source_id(None, "+919900000005")
    assert email_hash != phone_hash
    assert len(email_hash) == 16


def test_customer_hash_is_deterministic_and_case_normalised() -> None:
    a = compute_customer_source_id("Rohan@Example.com", None)
    b = compute_customer_source_id("rohan@example.com", None)
    assert a == b


def test_customer_hash_falls_back_to_phone_when_email_blank() -> None:
    blank_email = compute_customer_source_id("", "+919900000005")
    none_email = compute_customer_source_id(None, "+919900000005")
    assert blank_email == none_email
    assert len(blank_email) == 16


def test_missing_both_email_and_phone_raises_typed_error() -> None:
    row = _base_row()
    row["customer_email"] = None
    row["customer_phone"] = None
    with pytest.raises(MissingCustomerIdentityError) as exc_info:
        map_shiprocket_shipment(row)
    assert exc_info.value.code == "validation.missing_field"


def test_total_inr_is_decimal_not_float() -> None:
    row = _base_row()
    row["total"] = "1500.50"
    result = map_shiprocket_shipment(row)
    assert isinstance(result.total_inr, Decimal)
    assert result.total_inr == Decimal("1500.50")


def test_channel_order_id_stringified_for_shopify_join() -> None:
    row = _base_row()
    row["channel_order_id"] = 2001  # integer in source, must coerce
    result = map_shiprocket_shipment(row)
    assert result.channel_order_id == "2001"


def test_pincode_preserved_as_string_with_leading_zeros() -> None:
    row = _base_row()
    row["shipping_address"] = {"pincode": "000123"}
    result = map_shiprocket_shipment(row)
    assert result.pincode == "000123"
