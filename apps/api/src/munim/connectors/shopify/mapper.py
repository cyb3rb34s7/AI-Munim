"""Map a Shopify Admin API order payload to the canonical `Order` Pydantic.

This is the only place that knows the shape of Shopify's response. The rest
of the system reads from `Order`.

A malformed order (missing required field, unparseable date, etc.) raises;
the caller decides whether to fail the whole sync or skip the row. The
ShopifyConnector currently lets exceptions propagate (no silent fallbacks).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from munim.schemas import Order
from munim.shared.constants import PaymentMethod

_COD_GATEWAYS = {"cash_on_delivery", "cod"}


def map_shopify_order_to_normalized(raw: dict[str, Any]) -> Order:
    return Order(
        placed_at=_parse_iso(raw["created_at"]),
        total_inr=Decimal(raw["current_total_price"]),
        currency=raw.get("currency", "INR"),
        payment_method=_infer_payment_method(raw),
        financial_status=raw["financial_status"],
        fulfillment_status=raw.get("fulfillment_status"),
        pincode=_extract_pincode(raw),
        customer_source_id=_extract_customer_id(raw),
        utm_campaign=raw.get("source_name"),
        line_items_count=len(raw.get("line_items", [])),
    )


def _parse_iso(value: str) -> datetime:
    # Shopify sends "+05:30" style offsets; fromisoformat handles them in 3.11+.
    dt = datetime.fromisoformat(value)
    return dt.astimezone(tz=dt.tzinfo) if dt.tzinfo else dt


def _infer_payment_method(raw: dict[str, Any]) -> PaymentMethod:
    financial_status = raw.get("financial_status", "")
    gateways = [g.lower() for g in raw.get("payment_gateway_names", [])]

    if financial_status == "partially_paid":
        return PaymentMethod.PARTIAL
    if any(g in _COD_GATEWAYS for g in gateways):
        return PaymentMethod.COD
    return PaymentMethod.PREPAID


def _extract_pincode(raw: dict[str, Any]) -> str | None:
    shipping = raw.get("shipping_address") or {}
    zip_value = shipping.get("zip")
    return str(zip_value) if zip_value is not None else None


def _extract_customer_id(raw: dict[str, Any]) -> str | None:
    customer = raw.get("customer") or {}
    cid = customer.get("id")
    return str(cid) if cid is not None else None
