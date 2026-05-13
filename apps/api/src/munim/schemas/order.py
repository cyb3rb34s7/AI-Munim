"""Canonical normalized shape for an order, source-agnostic.

Per docs/architecture.md §4.2: this is the Pydantic model that lives in the
`normalized` JSON column of a `record` row when `entity_type='order'`.
Connectors map their source payload into this shape.

Money is `Decimal`, serialised as a string (per docs/conventions.md §8.1).
Time is timezone-aware UTC (per §8.2). Pincode is a string to preserve
leading zeros.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from munim.shared.constants import PaymentMethod


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placed_at: datetime
    total_inr: Decimal
    currency: str = "INR"
    payment_method: PaymentMethod
    financial_status: str
    fulfillment_status: str | None = None
    pincode: str | None = None
    customer_source_id: str | None = None
    utm_campaign: str | None = None
    line_items_count: int = Field(default=0, ge=0)
