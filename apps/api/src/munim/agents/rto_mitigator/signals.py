from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from munim.models import Record
from munim.shared.constants import EntityType, FulfillmentStatus, SourceSystem

_IST = ZoneInfo("Asia/Kolkata")

_HIGH_RISK_PINCODES: frozenset[str] = frozenset(
    {
        "110001",
        "110002",
        "700001",
        "700002",
        "560100",
        "000123",
    }
)

_LOW_VALUE_THRESHOLD = Decimal("1000")
_HIGH_VALUE_THRESHOLD = Decimal("5000")

_LATE_NIGHT_START_HOUR = 22
_LATE_NIGHT_END_HOUR = 6
_BUSINESS_HOURS_START = 9
_BUSINESS_HOURS_END = 18

_CONFIDENT_HISTORY_MIN = 3
_POPULATION_RTO_BASELINE = 0.20
_RTO_RATE_SIGNAL_MULTIPLIER = 1.5


@dataclass
class SignalResult:
    score: float
    diagnostic: dict[str, Any] = field(default_factory=dict)


def order_value_bucket(total_inr: Decimal) -> SignalResult:
    if total_inr < _LOW_VALUE_THRESHOLD:
        return SignalResult(score=0.2, diagnostic={"bucket": "low", "total_inr": str(total_inr)})
    if total_inr < _HIGH_VALUE_THRESHOLD:
        return SignalResult(score=0.5, diagnostic={"bucket": "medium", "total_inr": str(total_inr)})
    return SignalResult(score=0.8, diagnostic={"bucket": "high", "total_inr": str(total_inr)})


def pincode_risk(pincode: str | None) -> SignalResult:
    if pincode is None:
        return SignalResult(score=0.2, diagnostic={"pincode": None, "in_high_risk_list": False})
    in_list = pincode in _HIGH_RISK_PINCODES
    return SignalResult(
        score=0.7 if in_list else 0.2,
        diagnostic={"pincode": pincode, "in_high_risk_list": in_list},
    )


def time_of_order_risk(placed_at_iso: str) -> SignalResult:
    dt = datetime.fromisoformat(placed_at_iso)
    if dt.tzinfo is None:
        raise ValueError(
            f"placed_at must include a timezone offset; got naive datetime {placed_at_iso!r}"
        )
    dt_ist = dt.astimezone(_IST)
    hour = dt_ist.hour
    if hour >= _LATE_NIGHT_START_HOUR or hour < _LATE_NIGHT_END_HOUR:
        band = "late_night"
        score = 0.7
    elif _BUSINESS_HOURS_START <= hour < _BUSINESS_HOURS_END:
        band = "business_hours"
        score = 0.2
    else:
        band = "evening"
        score = 0.4
    return SignalResult(
        score=score,
        diagnostic={"hour_ist": hour, "hour_band": band, "placed_at": placed_at_iso},
    )


def customer_rto_rate(
    session: Session,
    merchant_id: str,
    customer_source_id: str | None,
) -> SignalResult:
    if customer_source_id is None or customer_source_id == "":
        return SignalResult(
            score=_POPULATION_RTO_BASELINE,
            diagnostic={
                "history_count": 0,
                "confident": False,
                "rate_source": "population_baseline",
                "customer_id_missing": True,
            },
        )
    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == SourceSystem.SHIPROCKET.value)
        .where(Record.entity_type == EntityType.SHIPMENT.value)
    ).all()
    customer_rows = [
        r for r in rows if r.normalized.get("customer_source_id") == customer_source_id
    ]
    history_count = len(customer_rows)
    confident = history_count >= _CONFIDENT_HISTORY_MIN

    if not confident:
        return SignalResult(
            score=_POPULATION_RTO_BASELINE,
            diagnostic={
                "history_count": history_count,
                "confident": False,
                "rate_source": "population_baseline",
            },
        )

    rto_count = sum(
        1
        for r in customer_rows
        if r.normalized.get("fulfillment_status") == FulfillmentStatus.RTO.value
    )
    rate = rto_count / history_count
    return SignalResult(
        score=min(rate * _RTO_RATE_SIGNAL_MULTIPLIER, 1.0),
        diagnostic={
            "history_count": history_count,
            "rto_count": rto_count,
            "observed_rate": rate,
            "saturation_multiplier": _RTO_RATE_SIGNAL_MULTIPLIER,
            "confident": True,
            "rate_source": "customer_history",
        },
    )
