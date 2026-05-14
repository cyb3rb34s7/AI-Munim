"""HTTP / fixture access to Shopify Admin API.

Demo mode reads a frozen fixture (Phase 2). Real mode (Phase 4) calls the
Shopify Admin API with the merchant's access token, follows the `Link`
header for cursor pagination, and retries on 429 with the suggested
Retry-After.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from munim.connectors.base import Credential
from munim.shared.config import get_settings
from munim.shared.constants import CredentialStatus
from munim.shared.crypto import validate_shop_domain

_DEFAULT_LIMIT = 250
_MAX_RETRIES_ON_429 = 5
_DEFAULT_RETRY_AFTER_SEC = 2.0
_LINK_NEXT_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')


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
        if status == CredentialStatus.CONNECTED.value:
            async for order in self._iter_real_orders():
                yield order
            return
        raise ValueError(
            f"Unsupported credential status {status!r}; expected 'demo' or 'connected'."
        )

    async def validate_credential(self) -> bool:
        """Real-mode credential check via GET /admin/api/{ver}/shop.json."""
        settings = get_settings()
        shop = self._credential.blob["shop"]
        # Defense in depth: even though the blob is AES-GCM-protected at rest,
        # re-validating the shop value here keeps each callsite self-defending
        # against any future write path that forgets to validate (per Phase 4
        # reviewer finding — SSRF gap).
        validate_shop_domain(shop)
        token = self._credential.blob["access_token"]
        url = f"https://{shop}/admin/api/{settings.shopify_api_version}/shop.json"
        response = await self._http_client.get(
            url,
            headers={"X-Shopify-Access-Token": token},
            timeout=15.0,
        )
        return response.status_code == 200

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

    async def _iter_real_orders(self) -> AsyncIterator[dict[str, Any]]:
        settings = get_settings()
        shop = self._credential.blob["shop"]
        # Defense in depth — see comment in validate_credential.
        validate_shop_domain(shop)
        token = self._credential.blob["access_token"]
        base_url = f"https://{shop}/admin/api/{settings.shopify_api_version}/orders.json"
        url: str | None = f"{base_url}?limit={_DEFAULT_LIMIT}&status=any"

        while url is not None:
            response = await self._get_with_429_retry(
                url, headers={"X-Shopify-Access-Token": token}
            )
            response.raise_for_status()  # any non-2xx propagates (caught in service)
            body = response.json()
            for order in body.get("orders", []):
                yield order
            url = _next_page_url(response.headers.get("link", ""))

    async def _get_with_429_retry(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
        attempt = 0
        while True:
            response = await self._http_client.get(url, headers=headers, timeout=30.0)
            if response.status_code != 429:
                return response
            attempt += 1
            if attempt > _MAX_RETRIES_ON_429:
                return response  # let raise_for_status surface it
            retry_after_header = response.headers.get("retry-after", "")
            try:
                retry_after = float(retry_after_header)
            except ValueError:
                retry_after = _DEFAULT_RETRY_AFTER_SEC
            await asyncio.sleep(retry_after)


def _next_page_url(link_header: str) -> str | None:
    match = _LINK_NEXT_PATTERN.search(link_header)
    return match.group(1) if match else None
