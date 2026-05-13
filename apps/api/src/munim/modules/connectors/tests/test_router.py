from fastapi.testclient import TestClient


def test_list_returns_envelope_with_shopify(client: TestClient) -> None:
    response = client.get("/connectors")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"].startswith("tr_")
    names = [c["name"] for c in body["data"]["connectors"]]
    assert "shopify" in names


def test_unconnected_shopify_status_is_null(client: TestClient) -> None:
    body = client.get("/connectors").json()
    shopify = next(c for c in body["data"]["connectors"] if c["name"] == "shopify")
    assert shopify["status"] is None
    assert shopify["last_sync_at"] is None


def test_connect_then_list_shows_demo_status(client: TestClient) -> None:
    client.post("/connectors/shopify/connect").raise_for_status()
    body = client.get("/connectors").json()
    shopify = next(c for c in body["data"]["connectors"] if c["name"] == "shopify")
    assert shopify["status"] == "demo"


def test_sync_returns_three_upserts_and_updates_counts(client: TestClient) -> None:
    # End-to-end at the HTTP boundary: connect → sync → counts visible.
    # If this passes, the demo works for a reviewer with no Python repl.
    client.post("/connectors/shopify/connect").raise_for_status()

    sync_response = client.post("/connectors/shopify/sync")
    assert sync_response.status_code == 200
    sync_body = sync_response.json()
    assert sync_body["data"]["rows_upserted"] == 3
    assert sync_body["data"]["rows_skipped"] == 0

    list_body = client.get("/connectors").json()
    shopify = next(c for c in list_body["data"]["connectors"] if c["name"] == "shopify")
    order_count = next(c["count"] for c in shopify["record_counts"] if c["entity_type"] == "order")
    assert order_count == 3
    assert shopify["last_sync_at"] is not None


def test_sync_without_connect_returns_typed_error_envelope(client: TestClient) -> None:
    # Per docs/conventions.md §10 — no silent fallback. The frontend branches
    # on `code`, so this must be 'connector.not_connected', not a generic 500.
    response = client.post("/connectors/shopify/sync")
    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.not_connected"
    assert body["trace_id"].startswith("tr_")


def test_unknown_connector_name_returns_404_envelope(client: TestClient) -> None:
    response = client.post("/connectors/woocommerce/connect")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.unknown"
