from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from munim.schemas import Order
from munim.shared.constants import PaymentMethod


def _base_order_kwargs() -> dict[str, Any]:
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
