"""ShopifyConnector — the first concrete implementation of `BaseConnector`.

Phase 2: `validate` (demo only) + `sync_full`.
Phase 4: `authorize_url` and `exchange_code` removed from BaseConnector ABC;
         real credential validate + client updated in the same phase (Task 7).
"""

from datetime import UTC, datetime
from typing import ClassVar

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.shopify.client import ShopifyClient
from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType


class ShopifyConnector(BaseConnector):
    name: ClassVar[ConnectorName] = ConnectorName.SHOPIFY

    async def validate(self, credential: Credential) -> bool:
        status = credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            return True
        raise NotImplementedError(f"Credential status {status!r} is not handled in validate.")

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
