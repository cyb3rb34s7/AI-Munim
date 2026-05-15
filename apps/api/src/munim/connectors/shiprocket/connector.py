"""ShiprocketConnector — demo-mode connector reading a frozen shipments fixture.

Same shape as MetaAdsConnector: 200ms sleep so the UI Syncing... state has
weight, fixture is package-internal, sync_full upserts via RowSink. The
RowSink natural key + payload_hash deliver idempotency across re-syncs.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.shiprocket.mapper import build_source_id, map_shiprocket_shipment
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType

_DEMO_SYNC_DELAY_SEC = 0.2
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "shipments.json"


class ShiprocketConnector(BaseConnector):
    name: ClassVar[ConnectorName] = ConnectorName.SHIPROCKET
    is_demo: ClassVar[bool] = True

    async def validate(self, credential: Credential) -> bool:
        status = credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            return True
        raise NotImplementedError(
            f"Shiprocket connector only supports demo credentials; got status={status!r}."
        )

    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        started_at = datetime.now(UTC)
        await asyncio.sleep(_DEMO_SYNC_DELAY_SEC)

        rows_upserted = 0
        rows_skipped = 0

        for raw in _load_fixture():
            normalized = map_shiprocket_shipment(raw)
            _, changed = ctx.row_sink.upsert(
                source_id=build_source_id(raw),
                entity_type=EntityType.SHIPMENT,
                raw=raw,
                normalized=normalized,
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


def _load_fixture() -> list[dict[str, Any]]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    data: list[dict[str, Any]] = payload["data"]
    return data
