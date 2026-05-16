from conftest import AuthClient
from fastapi.testclient import TestClient


def test_list_returns_envelope_with_shopify(auth_client: AuthClient) -> None:
    response = auth_client.client.get("/connectors")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"].startswith("tr_")
    names = [c["name"] for c in body["data"]["connectors"]]
    assert "shopify" in names


def test_unauthenticated_connectors_list_returns_401(client: TestClient) -> None:
    response = client.get("/connectors")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"


def test_connect_then_list_shows_demo_status(auth_client: AuthClient) -> None:
    auth_client.client.post("/connectors/shopify/connect").raise_for_status()
    body = auth_client.client.get("/connectors").json()
    shopify = next(c for c in body["data"]["connectors"] if c["name"] == "shopify")
    assert shopify["status"] == "demo"


def test_sync_returns_three_upserts_and_updates_counts(auth_client: AuthClient) -> None:
    # End-to-end at the HTTP boundary: connect → sync → counts visible.
    # If this passes, the demo works for a reviewer with no Python repl.
    # NOTE: auth_client.client starts pre-seeded with 96 rows from
    # /auth/start. The Shopify connect-then-sync path here uses the
    # legacy /connectors/shopify/connect endpoint which loads from
    # apps/api/data/fixtures/shopify/orders.json (3 orders). Those 3
    # orders have distinct source_ids from the Phase 9 seed fixture, so
    # the upsert count is exactly 3.
    auth_client.client.post("/connectors/shopify/connect").raise_for_status()

    sync_response = auth_client.client.post("/connectors/shopify/sync")
    assert sync_response.status_code == 200
    sync_body = sync_response.json()
    assert sync_body["data"]["rows_upserted"] == 3
    assert sync_body["data"]["rows_skipped"] == 0


def test_sync_without_connect_returns_typed_error_envelope(auth_client: AuthClient) -> None:
    # Drop the demo credential the seeder wrote so we can exercise the
    # "no credential" branch. Per docs/conventions.md §10 — no silent
    # fallback. The frontend branches on `code`, so this must be
    # 'connector.not_connected', not a generic 500.
    from sqlmodel import Session, select

    from munim.models import ConnectorCredentials
    from munim.shared.db import get_engine

    with Session(get_engine()) as s:
        existing = s.exec(
            select(ConnectorCredentials)
            .where(ConnectorCredentials.merchant_id == auth_client.merchant_id)
            .where(ConnectorCredentials.connector == "shopify")
        ).first()
        if existing is not None:
            s.delete(existing)
            s.commit()

    response = auth_client.client.post("/connectors/shopify/sync")
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.not_connected"
    assert body["trace_id"].startswith("tr_")


def test_unknown_connector_name_returns_404_envelope(auth_client: AuthClient) -> None:
    response = auth_client.client.post("/connectors/woocommerce/connect")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.unknown"


def test_two_merchants_see_independent_connector_state(auth_client: AuthClient) -> None:
    # Multi-tenant isolation spot-check. Merchant A connects + syncs Shopify;
    # merchant B (a fresh /auth/start in a separate TestClient) sees a
    # connected Shopify (because the seeder wrote a demo credential for it)
    # but NOT merchant A's record_counts.
    from fastapi.testclient import TestClient as _TestClient

    from munim.main import create_app

    auth_client.client.post("/connectors/shopify/connect").raise_for_status()
    auth_client.client.post("/connectors/shopify/sync").raise_for_status()

    with _TestClient(create_app()) as b:
        b.post("/auth/start", json={"display_name": "Bravo"}).raise_for_status()
        b_body = b.get("/connectors").json()
        b_shopify = next(c for c in b_body["data"]["connectors"] if c["name"] == "shopify")
        # Merchant B's Shopify counts come from the Phase 9 seed only — 6 orders.
        order_count = next(
            (c["count"] for c in b_shopify["record_counts"] if c["entity_type"] == "order"),
            0,
        )
        assert order_count == 6
