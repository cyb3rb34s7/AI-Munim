import httpx
import pytest
import respx

from munim.connectors.base import Credential
from munim.connectors.shopify.client import ShopifyClient
from munim.shared.constants import ConnectorName, CredentialStatus
from munim.shared.crypto import InvalidShopDomainError


def _connected_cred(shop: str = "munim-dev.myshopify.com") -> Credential:
    return Credential(
        merchant_id="m_default",
        connector=ConnectorName.SHOPIFY,
        blob={
            "status": CredentialStatus.CONNECTED.value,
            "shop": shop,
            "access_token": "shpat_test",
            "scopes": ["read_orders"],
        },
    )


@respx.mock
async def test_iter_orders_real_includes_access_token_header() -> None:
    # Real bug class: forgetting to attach the X-Shopify-Access-Token
    # would yield 401 on every page. This locks the header is set.
    route = respx.get("https://munim-dev.myshopify.com/admin/api/2026-04/orders.json").mock(
        return_value=httpx.Response(200, json={"orders": []})
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        async for _ in client.iter_orders():
            pass

    request = route.calls.last.request
    assert request.headers["X-Shopify-Access-Token"] == "shpat_test"


@respx.mock
async def test_iter_orders_follows_link_header_for_pagination() -> None:
    # Without pagination, anyone with >250 orders sees only the first page.
    base = "https://munim-dev.myshopify.com/admin/api/2026-04/orders.json"
    page2 = f"{base}?page_info=NEXT&limit=250"

    respx.get(base, params={"limit": "250", "status": "any"}).mock(
        return_value=httpx.Response(
            200,
            json={"orders": [{"id": 1}, {"id": 2}]},
            headers={"Link": f'<{page2}>; rel="next"'},
        )
    )
    respx.get(page2).mock(return_value=httpx.Response(200, json={"orders": [{"id": 3}]}))

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        ids = [o["id"] async for o in client.iter_orders()]

    assert ids == [1, 2, 3]


@respx.mock
async def test_iter_orders_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    # 429 with Retry-After is the actual Shopify rate limit response; if we
    # don't retry, a hot store can't be synced at all.
    base = "https://munim-dev.myshopify.com/admin/api/2026-04/orders.json"
    route = respx.get(base, params={"limit": "250", "status": "any"}).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0.01"}, json={"errors": "throttled"}),
            httpx.Response(200, json={"orders": [{"id": 7}]}),
        ]
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        ids = [o["id"] async for o in client.iter_orders()]

    assert ids == [7]
    assert route.call_count == 2


@respx.mock
async def test_validate_returns_true_when_shop_endpoint_returns_200() -> None:
    respx.get("https://munim-dev.myshopify.com/admin/api/2026-04/shop.json").mock(
        return_value=httpx.Response(200, json={"shop": {"id": 1}})
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        assert await client.validate_credential() is True


@respx.mock
async def test_validate_returns_false_on_401() -> None:
    # Real bug class: a revoked / wrong-shop token must NOT pass validate.
    respx.get("https://munim-dev.myshopify.com/admin/api/2026-04/shop.json").mock(
        return_value=httpx.Response(401, json={"errors": "Invalid API key"})
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        assert await client.validate_credential() is False


async def test_iter_orders_rejects_invalid_shop_in_blob_before_any_http_call() -> None:
    # Defense-in-depth (Phase 4 reviewer finding): even though the blob is
    # AES-GCM-protected at rest, the read path must self-defend against a
    # future write path that forgets validate_shop_domain. Asserting NO HTTP
    # call is made (respx not engaged) catches a regression where the read
    # path stops validating.
    bad = _connected_cred(shop="evil.attacker.com")
    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(bad, http_client)
        with pytest.raises(InvalidShopDomainError):
            async for _ in client.iter_orders():
                pass


async def test_validate_credential_rejects_invalid_shop_in_blob() -> None:
    # Same defense-in-depth check as iter_orders, on the validate path.
    bad = _connected_cred(shop="evil.attacker.com")
    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(bad, http_client)
        with pytest.raises(InvalidShopDomainError):
            await client.validate_credential()
