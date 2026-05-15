"""Map a Meta Marketing API `/insights` row to the normalized ad-spend payload.

Each input row is one (campaign, day) pair from Meta's `/insights` endpoint.
Spend, impressions, clicks, CTR, CPM are top-level fields. Conversions live in
a positional `actions` array keyed by `action_type`.

The output `date` is a date string, not a UTC timestamp: campaign-day spend is
naturally date-bucketed by Meta, with no time-of-day component. Treating it as
a date keeps the natural key stable across timezone debates.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError


class UnexpectedSpendValueError(MunimError):
    code = ErrorCode.VALIDATION_BAD_FORMAT.value
    http_status = 422
    message = "Meta ad-spend value could not be parsed as a Decimal."


_PURCHASE_ACTION = "purchase"
_ADD_TO_CART_ACTION = "add_to_cart"


class MetaAdSpend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    campaign_name: str
    date: str
    spend_inr: Decimal
    impressions: int
    clicks: int
    ctr: float
    cpm: float
    purchases_attributed: int
    add_to_carts_attributed: int


def map_meta_ads_insight(raw: dict[str, Any]) -> MetaAdSpend:
    spend_raw = raw["spend"]
    try:
        spend_inr = Decimal(spend_raw)
    except (InvalidOperation, TypeError) as exc:
        raise UnexpectedSpendValueError(
            message=f"Could not parse Meta spend value {spend_raw!r} as Decimal.",
            details={"campaign_id": raw.get("campaign_id"), "spend": spend_raw},
        ) from exc

    actions = raw.get("actions") or []
    purchases = _extract_action_value(actions, _PURCHASE_ACTION)
    add_to_carts = _extract_action_value(actions, _ADD_TO_CART_ACTION)

    return MetaAdSpend(
        campaign_id=raw["campaign_id"],
        campaign_name=raw["campaign_name"],
        date=raw["date_start"],
        spend_inr=spend_inr,
        impressions=int(raw["impressions"]),
        clicks=int(raw["clicks"]),
        ctr=float(raw["ctr"]),
        cpm=float(raw["cpm"]),
        purchases_attributed=purchases,
        add_to_carts_attributed=add_to_carts,
    )


def _extract_action_value(actions: list[dict[str, Any]], action_type: str) -> int:
    for entry in actions:
        if entry.get("action_type") == action_type:
            return int(entry["value"])
    return 0


def build_source_id(raw: dict[str, Any]) -> str:
    return f"{raw['campaign_id']}_{raw['date_start']}"
