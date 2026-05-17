import json
from pathlib import Path

import httpx

from munim.connectors.base import Credential
from munim.connectors.shopify.client import ShopifyClient
from munim.shared.constants import ConnectorName

_PACKAGE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "orders.json"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id="m_default",
        connector=ConnectorName.SHOPIFY,
        blob={"status": "demo"},
    )


async def test_iter_orders_yields_every_fixture_order_in_source_order() -> None:
    # Contract: the client must yield ALL orders from the package fixture,
    # preserving the source order. A drop, dedupe, or reorder here would
    # silently swallow data downstream — the connector's sync would just
    # count the survivors and report "success" with the wrong count.
    expected_ids = [
        order["id"] for order in json.loads(_PACKAGE_FIXTURE.read_text(encoding="utf-8"))["data"]
    ]
    client = ShopifyClient(_demo_credential(), httpx.AsyncClient())
    try:
        seen_ids = [order["id"] async for order in client.iter_orders()]
    finally:
        await client.aclose()
    assert seen_ids == expected_ids
