"""Map a Shiprocket `/v1/external/orders` row to the normalized shipment payload.

Shiprocket's `created_at` is an IST-naive timestamp ("2026-04-15 10:30:00"),
not an ISO 8601 string with offset. Per docs/conventions.md §8.2 (UTC on the
wire, IST at display), we attach IST tzinfo explicitly and convert to UTC at
the mapper boundary. Reading clock fields off the original IST-naive string
would silently mis-shift every shipment by 5:30.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from munim.shared.constants import ErrorCode, FulfillmentStatus
from munim.shared.errors import MunimError
from munim.shared.utils.customer_hash import (
    MissingCustomerIdentityError,
    compute_customer_source_id,
)

_IST = ZoneInfo("Asia/Kolkata")

_SHIPROCKET_STATUS_MAP: dict[str, FulfillmentStatus] = {
    "DELIVERED": FulfillmentStatus.FULFILLED,
    "RTO": FulfillmentStatus.RTO,
    "RTO INITIATED": FulfillmentStatus.RTO,
    "RTO DELIVERED": FulfillmentStatus.RTO,
    "IN-TRANSIT": FulfillmentStatus.IN_TRANSIT,
    "PICKUP SCHEDULED": FulfillmentStatus.PENDING,
    "CANCELED": FulfillmentStatus.CANCELLED,
    "CANCELLED": FulfillmentStatus.CANCELLED,
}


class MissingShipmentFieldError(MunimError):
    code = ErrorCode.VALIDATION_MISSING_FIELD.value
    http_status = 422
    message = "Shiprocket row is missing a required field."


class UnknownShipmentStatusError(MunimError):
    code = ErrorCode.VALIDATION_BAD_FORMAT.value
    http_status = 422
    message = "Shiprocket row has an unrecognised status."


class Shipment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_order_id: str
    customer_source_id: str
    fulfillment_status: FulfillmentStatus
    awb_code: str
    courier_name: str
    total_inr: Decimal
    placed_at: datetime
    pincode: str


def map_shiprocket_shipment(raw: dict[str, Any]) -> Shipment:
    email = raw.get("customer_email")
    phone = raw.get("customer_phone")
    customer_source_id = compute_customer_source_id(email, phone)
    fulfillment_status = _map_status(raw["status"])

    shipping_address = raw.get("shipping_address") or {}
    pincode_value = shipping_address.get("pincode")
    if pincode_value is None:
        raise MissingShipmentFieldError(
            message=f"Shiprocket row {raw.get('id')!r} is missing shipping_address.pincode.",
            details={"id": raw.get("id"), "field": "shipping_address.pincode"},
        )

    return Shipment(
        channel_order_id=str(raw["channel_order_id"]),
        customer_source_id=customer_source_id,
        fulfillment_status=fulfillment_status,
        awb_code=str(raw["awb_code"]),
        courier_name=str(raw["courier_name"]),
        total_inr=Decimal(str(raw["total"])),
        placed_at=_parse_ist_naive_to_utc(raw["created_at"]),
        pincode=str(pincode_value),
    )


def _map_status(raw_status: str) -> FulfillmentStatus:
    mapped = _SHIPROCKET_STATUS_MAP.get(raw_status.upper())
    if mapped is None:
        raise UnknownShipmentStatusError(
            message=f"Unknown Shiprocket status {raw_status!r}.",
            details={"status": raw_status, "known": sorted(_SHIPROCKET_STATUS_MAP)},
        )
    return mapped


def _parse_ist_naive_to_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_IST).astimezone(UTC)
    return dt.astimezone(UTC)


def build_source_id(raw: dict[str, Any]) -> str:
    return str(raw["id"])


__all__ = [
    "MissingCustomerIdentityError",
    "MissingShipmentFieldError",
    "Shipment",
    "UnknownShipmentStatusError",
    "build_source_id",
    "compute_customer_source_id",
    "map_shiprocket_shipment",
]
