import hashlib
import hmac
import time

import httpx
import respx
from fastapi.testclient import TestClient

from munim.shared.config import get_settings
from munim.shared.crypto import sign_state


def test_oauth_init_returns_authorize_url(client: TestClient) -> None:
    response = client.post(
        "/connectors/shopify/oauth/init",
        json={"shop": "munim-dev.myshopify.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["authorize_url"].startswith(
        "https://munim-dev.myshopify.com/admin/oauth/authorize?"
    )


def test_oauth_init_rejects_invalid_shop(client: TestClient) -> None:
    response = client.post(
        "/connectors/shopify/oauth/init",
        json={"shop": "evil.attacker.com"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "connector.invalid_shop_domain"


def test_oauth_callback_missing_params_returns_typed_error(client: TestClient) -> None:
    # Per §10: missing required callback params must not redirect silently.
    response = client.get("/connectors/shopify/oauth/callback?code=abc")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation.bad_format"


@respx.mock
def test_oauth_callback_full_flow_redirects_to_frontend(client: TestClient) -> None:
    settings = get_settings()
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": int(time.time()),
        },
        settings.credentials_encryption_key,
    )
    params = {
        "code": "abc",
        "state": state,
        "shop": "munim-dev.myshopify.com",
        "timestamp": str(int(time.time())),
    }
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    params["hmac"] = hmac.new(
        settings.shopify_client_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "shpat_x", "scope": "read_orders"})
    )

    response = client.get(
        "/connectors/shopify/oauth/callback",
        params=params,
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.endswith("/connectors?connected=shopify")


@respx.mock
def test_oauth_callback_with_bad_hmac_returns_typed_error(client: TestClient) -> None:
    settings = get_settings()
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": int(time.time()),
        },
        settings.credentials_encryption_key,
    )
    # Note: hmac is intentionally wrong.
    response = client.get(
        "/connectors/shopify/oauth/callback",
        params={
            "code": "abc",
            "state": state,
            "shop": "munim-dev.myshopify.com",
            "timestamp": "1",
            "hmac": "deadbeef",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "auth.hmac_mismatch"
