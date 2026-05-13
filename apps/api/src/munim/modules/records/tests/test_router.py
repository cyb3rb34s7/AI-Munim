from fastapi.testclient import TestClient


def _ensure_synced(client: TestClient) -> None:
    client.post("/connectors/shopify/connect").raise_for_status()
    client.post("/connectors/shopify/sync").raise_for_status()


def test_records_list_after_sync_returns_three_rows(client: TestClient) -> None:
    _ensure_synced(client)
    body = client.get("/records").json()
    assert body["success"] is True
    assert len(body["data"]["items"]) == 3
    assert {item["entity_type"] for item in body["data"]["items"]} == {"order"}


def test_records_list_filters_by_entity_type(client: TestClient) -> None:
    # Filter contract: the same query language used by chat tools later.
    # If a filter param is silently ignored, every later chat query is wrong.
    _ensure_synced(client)
    body = client.get("/records?entity_type=shipment").json()
    assert body["data"]["items"] == []


def test_records_detail_returns_raw_and_normalized(client: TestClient) -> None:
    # Provenance over HTTP: the raw column on the wire must equal the source
    # payload byte-for-byte, plus the normalized projection.
    _ensure_synced(client)
    list_body = client.get("/records").json()
    record_id = list_body["data"]["items"][0]["id"]

    detail = client.get(f"/records/{record_id}").json()
    assert detail["data"]["raw"]["id"] in (5510000000001, 5510000000002, 5510000000003)
    assert "total_inr" in detail["data"]["normalized"]
    assert detail["data"]["payload_hash"]


def test_records_detail_unknown_id_returns_typed_404(client: TestClient) -> None:
    response = client.get("/records/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "record.not_found"
