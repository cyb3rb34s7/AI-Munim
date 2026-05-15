"""MetaAdsConnector — demo-mode connector reading a frozen `/insights` fixture.

Real-mode swap is mechanical: replace `_load_fixture` with an HTTP call to
Meta's Marketing API `/insights` endpoint, paginate, and yield the same row
shape. The mapper and the RowSink path stay unchanged.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from munim.connectors.base import BaseConnector, Credential, SyncContext, SyncResult
from munim.connectors.meta_ads.mapper import build_source_id, map_meta_ads_insight
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType

_DEMO_SYNC_DELAY_SEC = 0.2
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "insights.json"


class MetaAdsConnector(BaseConnector):
    name: ClassVar[ConnectorName] = ConnectorName.META_ADS
    is_demo: ClassVar[bool] = True

    async def validate(self, credential: Credential) -> bool:
        status = credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            return True
        raise NotImplementedError(
            f"Meta Ads connector only supports demo credentials; got status={status!r}."
        )

    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        started_at = datetime.now(UTC)
        await asyncio.sleep(_DEMO_SYNC_DELAY_SEC)

        rows_upserted = 0
        rows_skipped = 0

        for raw in _load_fixture():
            normalized = map_meta_ads_insight(raw)
            _, changed = ctx.row_sink.upsert(
                source_id=build_source_id(raw),
                entity_type=EntityType.AD_SPEND,
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
