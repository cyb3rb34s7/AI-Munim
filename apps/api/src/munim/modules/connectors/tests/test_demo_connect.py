from conftest import AuthClient
from sqlmodel import Session, select

from munim.models import ConnectorCredentials


def test_connect_demo_writes_credentials_row_with_demo_status(auth_client: AuthClient) -> None:
    from munim.shared.db import get_engine

    resp = auth_client.client.post("/connectors/meta_ads/connect-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["connector"]["name"] == "meta_ads"
    assert body["data"]["connector"]["status"] == "demo"
    assert body["data"]["connector"]["is_demo"] is True

    with Session(get_engine()) as session:
        row = session.exec(
            select(ConnectorCredentials)
            .where(ConnectorCredentials.merchant_id == auth_client.merchant_id)
            .where(ConnectorCredentials.connector == "meta_ads")
        ).one()
        assert row.status == "demo"


def test_connect_demo_is_idempotent_for_repeat_clicks(auth_client: AuthClient) -> None:
    first = auth_client.client.post("/connectors/shiprocket/connect-demo")
    second = auth_client.client.post("/connectors/shiprocket/connect-demo")
    assert first.status_code == 200
    assert second.status_code == 200

    from munim.shared.db import get_engine

    with Session(get_engine()) as session:
        rows = session.exec(
            select(ConnectorCredentials)
            .where(ConnectorCredentials.merchant_id == auth_client.merchant_id)
            .where(ConnectorCredentials.connector == "shiprocket")
        ).all()
        assert len(rows) == 1


def test_connect_demo_rejects_non_demo_connector(auth_client: AuthClient) -> None:
    resp = auth_client.client.post("/connectors/shopify/connect-demo")
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.not_demo"


def test_connect_demo_rejects_unknown_connector(auth_client: AuthClient) -> None:
    resp = auth_client.client.post("/connectors/madeup/connect-demo")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "connector.unknown"
