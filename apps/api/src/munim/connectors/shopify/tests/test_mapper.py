import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.shared.constants import PaymentMethod

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "orders.json"


@pytest.fixture(scope="module")
def fixture_orders() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        data: list[dict[str, Any]] = json.load(handle)["orders"]
        return data


def test_maps_cod_order_to_decimal_total_inr(fixture_orders: list[dict[str, Any]]) -> None:
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)

    assert order.total_inr == Decimal("1249.00")
    assert isinstance(order.total_inr, Decimal)
    assert order.payment_method is PaymentMethod.COD
    assert order.currency == "INR"


def test_maps_placed_at_to_utc(fixture_orders: list[dict[str, Any]]) -> None:
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)

    # Shopify sends +05:30; we store UTC.
    assert order.placed_at == datetime(2026, 5, 10, 3, 45, 32, tzinfo=UTC)
    assert order.placed_at.tzinfo is not None


def test_maps_prepaid_order(fixture_orders: list[dict[str, Any]]) -> None:
    prepaid_order = next(o for o in fixture_orders if o["id"] == 5510000000002)
    order = map_shopify_order_to_normalized(prepaid_order)

    assert order.payment_method is PaymentMethod.PREPAID
    assert order.total_inr == Decimal("2199.00")
    assert order.fulfillment_status == "fulfilled"


def test_maps_partial_order_and_preserves_leading_zero_pincode(
    fixture_orders: list[dict[str, Any]],
) -> None:
    partial_order = next(o for o in fixture_orders if o["id"] == 5510000000003)
    order = map_shopify_order_to_normalized(partial_order)

    assert order.payment_method is PaymentMethod.PARTIAL
    assert order.pincode == "000123"


def test_customer_source_id_is_string_even_when_shopify_returns_int(
    fixture_orders: list[dict[str, Any]],
) -> None:
    # Real bug class: Shopify sends customer.id as a JSON number. If we don't
    # explicitly stringify, the typed schema would fail or — worse — store an
    # int in a `str | None` field via Python's duck-typing and break joins.
    cod_order = next(o for o in fixture_orders if o["id"] == 5510000000001)
    order = map_shopify_order_to_normalized(cod_order)
    assert order.customer_source_id == "7700000000001"


def test_mapper_handles_missing_customer_for_guest_checkout() -> None:
    # Real Shopify edge case: guest checkouts have no customer object. The
    # connector must NOT crash on this — it has to record the order with
    # customer_source_id=None and continue. If we ever lose this branch the
    # sync would die mid-batch on a real store.
    guest_raw = {
        "id": 5510000000099,
        "created_at": "2026-05-12T11:00:00+05:30",
        "currency": "INR",
        "current_total_price": "499.00",
        "financial_status": "paid",
        "fulfillment_status": None,
        "payment_gateway_names": ["razorpay"],
        "customer": None,
        "shipping_address": {"zip": "560002", "city": "Bengaluru", "country_code": "IN"},
        "line_items": [{"id": 99, "name": "Sticker", "quantity": 1, "price": "499.00"}],
    }

    order = map_shopify_order_to_normalized(guest_raw)
    assert order.customer_source_id is None
    assert order.payment_method is PaymentMethod.PREPAID


def test_mapper_preserves_non_inr_currency_instead_of_defaulting() -> None:
    # The Order schema defaults currency="INR" if absent. The mapper must
    # NOT silently use that default when the source actually sends a value —
    # that would mask a multi-currency bug at the worst possible moment.
    usd_raw = {
        "id": 5510000000200,
        "created_at": "2026-05-12T12:00:00+05:30",
        "currency": "USD",
        "current_total_price": "29.99",
        "financial_status": "paid",
        "fulfillment_status": None,
        "payment_gateway_names": ["stripe"],
        "customer": {"id": 12345, "email": "x@example.com"},
        "shipping_address": {"zip": "94110", "city": "SF", "country_code": "US"},
        "line_items": [],
    }

    order = map_shopify_order_to_normalized(usd_raw)
    assert order.currency == "USD"


def test_mapper_raises_on_missing_required_field() -> None:
    # Per docs/conventions.md §10: no silent fallbacks. A malformed source
    # payload must raise so the sync fails loudly, not silently skip rows
    # while reporting "success".
    malformed = {
        "id": 5510000000300,
        # 'created_at' missing — a real Shopify response would never omit
        # this, so its absence is a real signal of upstream corruption.
        "currency": "INR",
        "current_total_price": "100.00",
        "financial_status": "paid",
        "payment_gateway_names": ["razorpay"],
    }

    with pytest.raises(KeyError):
        map_shopify_order_to_normalized(malformed)
