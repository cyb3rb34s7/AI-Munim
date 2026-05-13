import httpx

from munim.connectors.base import Credential
from munim.connectors.shopify.client import ShopifyClient
from munim.connectors.shopify.tests._paths import SHOPIFY_DEMO_FIXTURE_PATH as FIXTURE_PATH
from munim.shared.constants import ConnectorName


def _demo_credential() -> Credential:
    return Credential(
        merchant_id="m_default",
        connector=ConnectorName.SHOPIFY,
        blob={"status": "demo", "fixture_path": str(FIXTURE_PATH)},
    )


async def test_iter_orders_yields_every_fixture_order_in_source_order() -> None:
    # Contract: the client must yield ALL orders from the fixture, preserving
    # the source order. A drop, dedupe, or reorder here would silently swallow
    # data downstream — the connector's sync would just count the survivors
    # and report "success" with the wrong count.
    client = ShopifyClient(_demo_credential(), httpx.AsyncClient())
    try:
        seen_ids = [order["id"] async for order in client.iter_orders()]
    finally:
        await client.aclose()
    assert seen_ids == [5510000000001, 5510000000002, 5510000000003]
