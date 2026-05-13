"""HTTP / fixture access to Shopify Admin API.

Phase 2: demo-only. The client reads a frozen JSON fixture pointed to by
`Credential.blob["fixture_path"]` and yields its `orders` array. No network.

Phase 3 will add the real path: build the Admin URL, page through results,
honour rate limits. The interface (`iter_orders`) stays the same so the
connector layer does not change.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from munim.connectors.base import Credential
from munim.shared.constants import CredentialStatus


class ShopifyClient:
    def __init__(self, credential: Credential, http_client: httpx.AsyncClient) -> None:
        self._credential = credential
        self._http_client = http_client

    async def iter_orders(self) -> AsyncIterator[dict[str, Any]]:
        status = self._credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            async for order in self._iter_demo_orders():
                yield order
            return

        raise NotImplementedError(
            "Real Shopify Admin API access lands in Phase 3. Use a demo credential for now."
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def _iter_demo_orders(self) -> AsyncIterator[dict[str, Any]]:
        fixture_path_str = self._credential.blob.get("fixture_path")
        if not fixture_path_str:
            raise ValueError(
                "Demo credential is missing 'fixture_path' — set blob['fixture_path']."
            )

        fixture_path = Path(fixture_path_str)
        with fixture_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        for order in payload["orders"]:
            yield order
