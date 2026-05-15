from fastapi.testclient import TestClient
from sqlmodel import Session, select

from munim.models import ConnectorCredentials


def test_connect_demo_writes_credentials_row_with_demo_status(client: TestClient) -> None:
    from munim.shared.db import get_engine

    resp = client.post("/connectors/meta_ads/connect-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["connector"]["name"] == "meta_ads"
    assert body["data"]["connector"]["status"] == "demo"
    assert body["data"]["connector"]["is_demo"] is True

    with Session(get_engine()) as session:
        row = session.exec(
            select(ConnectorCredentials).where(ConnectorCredentials.connector == "meta_ads")
        ).one()
        assert row.status == "demo"


def test_connect_demo_is_idempotent_for_repeat_clicks(client: TestClient) -> None:
    first = client.post("/connectors/shiprocket/connect-demo")
    second = client.post("/connectors/shiprocket/connect-demo")
    assert first.status_code == 200
    assert second.status_code == 200

    from munim.shared.db import get_engine

    with Session(get_engine()) as session:
        rows = session.exec(
            select(ConnectorCredentials).where(ConnectorCredentials.connector == "shiprocket")
        ).all()
        assert len(rows) == 1


def test_connect_demo_rejects_non_demo_connector(client: TestClient) -> None:
    resp = client.post("/connectors/shopify/connect-demo")
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.not_demo"


def test_connect_demo_rejects_unknown_connector(client: TestClient) -> None:
    resp = client.post("/connectors/madeup/connect-demo")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.unknown"
