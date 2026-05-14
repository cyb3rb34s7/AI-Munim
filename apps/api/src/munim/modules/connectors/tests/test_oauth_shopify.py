from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from munim.modules.connectors.oauth_shopify import (
    OAuthExchangeError,
    build_shopify_authorize_url,
    exchange_shopify_code,
)


def test_authorize_url_targets_the_correct_shop_with_scopes_and_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("SHOPIFY_OAUTH_REDIRECT_URI", "http://localhost:8000/cb")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)  # 32 bytes decoded
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    url = build_shopify_authorize_url(
        merchant_id="m_default",
        shop="munim-dev.myshopify.com",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "munim-dev.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"

    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["test_client_id"]
    assert qs["redirect_uri"] == ["http://localhost:8000/cb"]
    scope_value = qs["scope"][0]
    for required in ("read_orders", "read_customers", "read_products"):
        assert required in scope_value
    # State must round-trip through verify_state for the callback to accept it.
    from munim.shared.crypto import verify_state

    state_payload = verify_state(qs["state"][0], "A" * 43)
    assert state_payload["merchant_id"] == "m_default"
    assert state_payload["shop"] == "munim-dev.myshopify.com"


def test_authorize_url_rejects_invalid_shop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "x")
    monkeypatch.setenv("SHOPIFY_OAUTH_REDIRECT_URI", "http://localhost:8000/cb")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings
    from munim.shared.crypto import InvalidShopDomainError

    get_settings.cache_clear()
    with pytest.raises(InvalidShopDomainError):
        build_shopify_authorize_url(
            merchant_id="m_default",
            shop="evil.attacker.com",
        )


@respx.mock
async def test_exchange_code_returns_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    route = respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "shpat_realtoken",
                "scope": "read_orders,read_customers",
            },
        )
    )

    async with httpx.AsyncClient() as client:
        token = await exchange_shopify_code(
            client,
            shop="munim-dev.myshopify.com",
            code="abc123",
        )

    assert token.access_token == "shpat_realtoken"
    assert token.scopes == ["read_orders", "read_customers"]
    # Verify the request body had the expected fields (not just status 200).
    request = route.calls.last.request
    body = dict(p.split("=") for p in request.content.decode().split("&"))
    assert body["client_id"] == "test_id"
    assert body["client_secret"] == "test_secret"
    assert body["code"] == "abc123"


@respx.mock
async def test_exchange_code_raises_typed_error_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(401, json={"error": "invalid_request"})
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(OAuthExchangeError) as exc_info:
            await exchange_shopify_code(
                client,
                shop="munim-dev.myshopify.com",
                code="bad",
            )
    assert exc_info.value.code == "auth.oauth_exchange_failed"
