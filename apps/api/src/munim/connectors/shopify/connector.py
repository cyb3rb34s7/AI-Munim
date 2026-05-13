"""ShopifyConnector — the first concrete implementation of `BaseConnector`.

Phase 2: only `validate` and `sync_full` work, and only against demo
credentials. `authorize_url` / `exchange_code` / real-credential paths raise
NotImplementedError and are completed in Phase 3.
"""

from datetime import UTC, datetime
from typing import ClassVar

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.shopify.client import ShopifyClient
from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType


class ShopifyConnector(BaseConnector):
    name: ClassVar[ConnectorName] = ConnectorName.SHOPIFY

    def authorize_url(self, merchant_id: str) -> str:
        raise NotImplementedError("OAuth UI lands in Phase 3. Use a demo credential for Phase 2.")

    async def exchange_code(self, merchant_id: str, code: str) -> Credential:
        raise NotImplementedError("OAuth UI lands in Phase 3. Use a demo credential for Phase 2.")

    async def validate(self, credential: Credential) -> bool:
        if credential.blob.get("status") == CredentialStatus.DEMO.value:
            return True
        raise NotImplementedError("Real Shopify credential validation lands in Phase 3.")

    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        started_at = datetime.now(UTC)
        client = ShopifyClient(ctx.credential, ctx.http_client)

        rows_upserted = 0
        rows_skipped = 0

        async for raw_order in client.iter_orders():
            order = map_shopify_order_to_normalized(raw_order)
            _, changed = ctx.row_sink.upsert(
                source_id=str(raw_order["id"]),
                entity_type=EntityType.ORDER,
                raw=raw_order,
                normalized=order,
            )
            if changed:
                rows_upserted += 1
            else:
                rows_skipped += 1

        return SyncResult(
            rows_upserted=rows_upserted,
            rows_skipped=rows_skipped,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
