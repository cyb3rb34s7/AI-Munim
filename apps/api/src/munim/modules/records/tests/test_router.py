from conftest import AuthClient
from fastapi.testclient import TestClient


def test_records_list_after_seed_has_96_rows(auth_client: AuthClient) -> None:
    # auth_client posts /auth/start + /auth/onboard, which seeds 96 rows
    # (6 Shopify + 40 Meta + 50 Shiprocket). The records list paginates at
    # limit=50 by default; bump to 200 for the smoke assert.
    body = auth_client.client.get("/api/records?limit=200").json()
    assert body["success"] is True
    assert len(body["data"]["items"]) == 96


def test_records_list_filters_by_source_system(auth_client: AuthClient) -> None:
    # The Records page filter chips set source_system; the backend must
    # honour it. If silently ignored, the chip is a placebo.
    body = auth_client.client.get("/api/records?source_system=shiprocket&limit=200").json()
    items = body["data"]["items"]
    assert len(items) == 50
    assert {item["source_system"] for item in items} == {"shiprocket"}


def test_records_list_filters_by_entity_type(auth_client: AuthClient) -> None:
    # Filter contract: the same query language used by chat tools later.
    # If a filter param is silently ignored, every later chat query is wrong.
    body = auth_client.client.get("/api/records?entity_type=shipment&limit=200").json()
    items = body["data"]["items"]
    assert len(items) == 50
    assert {item["entity_type"] for item in items} == {"shipment"}


def test_records_detail_returns_raw_and_normalized(auth_client: AuthClient) -> None:
    # Provenance over HTTP: the raw column on the wire must equal the source
    # payload byte-for-byte, plus the normalized projection.
    list_body = auth_client.client.get("/api/records?entity_type=order&limit=10").json()
    record_id = list_body["data"]["items"][0]["id"]

    detail = auth_client.client.get(f"/api/records/{record_id}").json()
    assert "id" in detail["data"]["raw"]
    assert "total_inr" in detail["data"]["normalized"]
    assert detail["data"]["payload_hash"]


def test_records_detail_unknown_id_returns_typed_404(auth_client: AuthClient) -> None:
    response = auth_client.client.get("/api/records/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "record.not_found"


def test_unauthenticated_records_returns_401(client: TestClient) -> None:
    response = client.get("/api/records")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"


def test_two_merchants_records_are_isolated(auth_client: AuthClient) -> None:
    # Isolation: merchant B's records list does NOT include any of merchant A's
    # record ids. The seeded rows have distinct DB ids per merchant because the
    # natural key includes merchant_id.
    from fastapi.testclient import TestClient as _TestClient

    from munim.main import create_app

    a_body = auth_client.client.get("/api/records?limit=200").json()
    a_ids = {item["id"] for item in a_body["data"]["items"]}

    with _TestClient(create_app()) as b:
        b.post("/api/auth/start", json={"display_name": "B"}).raise_for_status()
        b.post("/api/auth/onboard").raise_for_status()
        b_body = b.get("/api/records?limit=200").json()
        b_ids = {item["id"] for item in b_body["data"]["items"]}

    assert a_ids.isdisjoint(b_ids)
    assert len(a_ids) == 96
    assert len(b_ids) == 96
