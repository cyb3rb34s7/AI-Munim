from datetime import UTC, datetime
from typing import Any

from conftest import AuthClient
from fastapi.testclient import TestClient

from munim.models import Record
from munim.shared.constants import (
    EntityType,
    FulfillmentStatus,
    PaymentMethod,
    SourceSystem,
)


def _seed_cod_order(session: Any, merchant_id: str, source_id: str) -> None:
    row = Record(
        merchant_id=merchant_id,
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


def test_trigger_agent_returns_summary(auth_client: AuthClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine

    with Session(get_engine()) as s:
        _seed_cod_order(s, auth_client.merchant_id, "cod_smoke")

    response = auth_client.client.post("/agents/rto_mitigator/run")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["run"]["agent"] == "rto_mitigator"
    # /auth/start seeds 2 COD Shopify orders (rohan + amit) plus the
    # one we added above = 3. The agent scans all COD orders for the
    # merchant.
    assert body["data"]["run"]["orders_scanned"] == 3


def test_trigger_unknown_agent_returns_404(auth_client: AuthClient) -> None:
    response = auth_client.client.post("/agents/madeup/run")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "agent.unknown"


def test_list_agent_runs_returns_summaries(auth_client: AuthClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine

    with Session(get_engine()) as s:
        _seed_cod_order(s, auth_client.merchant_id, "cod_list_1")

    auth_client.client.post("/agents/rto_mitigator/run").raise_for_status()
    response = auth_client.client.get("/agent-runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]["items"]) >= 1
    assert body["data"]["items"][0]["agent"] == "rto_mitigator"


def test_get_agent_run_returns_decisions(auth_client: AuthClient) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine

    with Session(get_engine()) as s:
        for i in range(3):
            row = Record(
                merchant_id=auth_client.merchant_id,
                source_system=SourceSystem.SHIPROCKET.value,
                source_id=f"hist_rto_{i}",
                entity_type=EntityType.SHIPMENT.value,
                fetched_at=datetime.now(UTC),
                payload_hash=f"h_hist_rto_{i}",
                raw={"id": f"hist_rto_{i}"},
                normalized={
                    "customer_source_id": "cust_x",
                    "fulfillment_status": FulfillmentStatus.RTO.value,
                    "channel_order_id": f"hist_rto_{i}",
                    "awb_code": f"AWB_{i}",
                    "courier_name": "Test Courier",
                    "total_inr": "1000.00",
                    "placed_at": "2026-05-01T05:00:00+00:00",
                    "pincode": "110001",
                },
            )
            s.add(row)
        s.commit()
        _seed_cod_order(s, auth_client.merchant_id, "cod_detail")

    trigger_body = auth_client.client.post("/agents/rto_mitigator/run").json()
    run_log_id = trigger_body["data"]["run"]["run_log_id"]

    response = auth_client.client.get(f"/agent-runs/{run_log_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["run_log_id"] == run_log_id
    detail = next(d for d in body["data"]["decisions"] if d["source_id"] == "cod_detail")
    assert detail["action"] == "convert_to_prepaid"


def test_get_unknown_agent_run_returns_typed_404(auth_client: AuthClient) -> None:
    response = auth_client.client.get("/agent-runs/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "agent.run_not_found"


def test_unauthenticated_trigger_returns_401(client: TestClient) -> None:
    response = client.post("/agents/rto_mitigator/run")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"


def test_two_merchants_agent_runs_are_isolated(auth_client: AuthClient) -> None:
    # Trigger an agent run for merchant A; merchant B's list MUST NOT
    # include any of A's run ids. This is the third spot-check on the
    # isolation claim (alongside records + connectors).
    from fastapi.testclient import TestClient as _TestClient

    from munim.main import create_app

    auth_client.client.post("/agents/rto_mitigator/run").raise_for_status()
    a_ids = {
        item["run_log_id"] for item in auth_client.client.get("/agent-runs").json()["data"]["items"]
    }

    with _TestClient(create_app()) as b:
        b.post("/auth/start", json={"display_name": "Bravo"}).raise_for_status()
        b.post("/agents/rto_mitigator/run").raise_for_status()
        b_ids = {item["run_log_id"] for item in b.get("/agent-runs").json()["data"]["items"]}

    assert a_ids.isdisjoint(b_ids)
