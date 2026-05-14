from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from munim.models import Record
from munim.shared.constants import EntityType, PaymentMethod, SourceSystem


def _seed_cod_order(session: Any, source_id: str) -> None:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized={
            "placed_at": "2026-05-10T23:45:00+05:30",
            "total_inr": "6000",
            "currency": "INR",
            "payment_method": PaymentMethod.COD.value,
            "financial_status": "pending",
            "pincode": "110001",
            "customer_source_id": "cust_x",
        },
    )
    session.add(row)
    session.commit()


def test_trigger_agent_returns_summary(client: TestClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine, init_db

    init_db()
    with Session(get_engine()) as s:
        _seed_cod_order(s, "cod_smoke")

    response = client.post("/agents/rto_mitigator/run")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["run"]["agent"] == "rto_mitigator"
    assert body["data"]["run"]["orders_scanned"] == 1


def test_trigger_unknown_agent_returns_404(client: TestClient) -> None:
    response = client.post("/agents/madeup/run")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "agent.unknown"


def test_list_agent_runs_returns_summaries(client: TestClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine, init_db

    init_db()
    with Session(get_engine()) as s:
        _seed_cod_order(s, "cod_list_1")

    client.post("/agents/rto_mitigator/run").raise_for_status()
    response = client.get("/agent-runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]["items"]) >= 1
    assert body["data"]["items"][0]["agent"] == "rto_mitigator"


def test_get_agent_run_returns_decisions(client: TestClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine, init_db

    init_db()
    with Session(get_engine()) as s:
        for i in range(3):
            row = Record(
                merchant_id="m_default",
                source_system=SourceSystem.SHOPIFY.value,
                source_id=f"hist_rto_{i}",
                entity_type=EntityType.ORDER.value,
                fetched_at=datetime.now(UTC),
                payload_hash=f"h_hist_rto_{i}",
                raw={"id": f"hist_rto_{i}"},
                normalized={
                    "placed_at": "2026-05-08T12:00:00+05:30",
                    "total_inr": "1000",
                    "currency": "INR",
                    "payment_method": PaymentMethod.COD.value,
                    "financial_status": "pending",
                    "fulfillment_status": "rto",
                    "pincode": "110001",
                    "customer_source_id": "cust_x",
                },
            )
            s.add(row)
        s.commit()
        _seed_cod_order(s, "cod_detail")

    trigger_body = client.post("/agents/rto_mitigator/run").json()
    run_log_id = trigger_body["data"]["run"]["run_log_id"]

    response = client.get(f"/agent-runs/{run_log_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["run_log_id"] == run_log_id
    detail = next(d for d in body["data"]["decisions"] if d["source_id"] == "cod_detail")
    assert detail["action"] == "convert_to_prepaid"


def test_get_unknown_agent_run_returns_typed_404(client: TestClient) -> None:
    response = client.get("/agent-runs/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "record.not_found"
