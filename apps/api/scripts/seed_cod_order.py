"""Seed two COD orders into the local dev DB for the agent demo.

Shopify's `draftOrderComplete(paymentPending: true)` does not populate
`payment_gateway_names`, so the mapper falls through to PREPAID and the agent
filters the order out. Until we have a Shopify path that produces a real COD
order, this script seeds local-only rows so the agent has something to score.

The seeded customers match Customer A (rohan@example.com — 3/5 RTO history)
and Customer B (priya@example.com — 5/5 delivered) from the Shiprocket fixture
so the RTO agent's customer_rto_rate signal demonstrates the cross-connector
join. Run after `POST /connectors/shiprocket/connect-demo + sync` for the
demo narrative to land.
"""

from datetime import UTC, datetime

from sqlmodel import Session, select

from munim.models import Record
from munim.shared.constants import EntityType, PaymentMethod, SourceSystem
from munim.shared.db import DEFAULT_MERCHANT_ID, get_engine, init_db
from munim.shared.utils.customer_hash import compute_customer_source_id


def _build_row(source_id: str, customer_email: str, *, pincode: str) -> Record:
    return Record(
        merchant_id=DEFAULT_MERCHANT_ID,
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id, "source": "agent-demo-seed"},
        normalized={
            "placed_at": "2026-05-14T23:45:00+05:30",
            "total_inr": "6000.00",
            "currency": "INR",
            "payment_method": PaymentMethod.COD.value,
            "financial_status": "pending",
            "pincode": pincode,
            "customer_source_id": compute_customer_source_id(customer_email, None),
            "utm_campaign": "demo",
            "line_items_count": 2,
        },
    )


def main() -> None:
    init_db()
    seeds = [
        ("seed_cod_high_risk", "rohan@example.com", "110001"),
        ("seed_cod_clean", "priya@example.com", "560001"),
    ]
    with Session(get_engine()) as session:
        for source_id, email, pincode in seeds:
            existing = session.exec(
                select(Record)
                .where(Record.merchant_id == DEFAULT_MERCHANT_ID)
                .where(Record.source_system == SourceSystem.SHOPIFY.value)
                .where(Record.source_id == source_id)
            ).first()
            if existing is not None:
                print(f"Already seeded {source_id} (id={existing.id}); skipping.")
                continue
            row = _build_row(source_id, email, pincode=pincode)
            session.add(row)
            session.commit()
            print(f"Seeded {source_id} (id={row.id}, customer={email}).")


if __name__ == "__main__":
    main()
