"""Seed one high-RTO-risk COD order into the local dev DB for the agent demo.

Shopify's `draftOrderComplete(paymentPending: true)` does not populate
`payment_gateway_names`, so the mapper falls through to PREPAID and the agent
filters the order out. Until we have a Shopify path that produces a real COD
order, this script seeds one local-only row so the agent has something to score.
"""

from datetime import UTC, datetime

from sqlmodel import Session

from munim.models import Record
from munim.shared.constants import EntityType, PaymentMethod, SourceSystem
from munim.shared.db import DEFAULT_MERCHANT_ID, get_engine, init_db


def main() -> None:
    init_db()
    with Session(get_engine()) as session:
        row = Record(
            merchant_id=DEFAULT_MERCHANT_ID,
            source_system=SourceSystem.SHOPIFY.value,
            source_id="seed_cod_demo",
            entity_type=EntityType.ORDER.value,
            fetched_at=datetime.now(UTC),
            payload_hash="seed_cod_h",
            raw={"id": "seed_cod_demo", "source": "agent-demo-seed"},
            normalized={
                "placed_at": "2026-05-14T23:45:00+05:30",
                "total_inr": "6000.00",
                "currency": "INR",
                "payment_method": PaymentMethod.COD.value,
                "financial_status": "pending",
                "fulfillment_status": None,
                "pincode": "110001",
                "customer_source_id": "seed_cust_high_risk",
                "utm_campaign": "demo",
                "line_items_count": 2,
            },
        )
        session.add(row)
        session.commit()
        print(f"Seeded COD demo row id={row.id}")


if __name__ == "__main__":
    main()
