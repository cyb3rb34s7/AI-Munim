from decimal import Decimal

import httpx
from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.meta_ads.connector import MetaAdsConnector
from munim.models import Record
from munim.shared.constants import ConnectorName, CredentialStatus, EntityType, SourceSystem

DEFAULT_MERCHANT_ID = "m_default"


def _demo_credential() -> Credential:
    return Credential(
        merchant_id=DEFAULT_MERCHANT_ID,
        connector=ConnectorName.META_ADS,
        blob={"status": CredentialStatus.DEMO.value},
    )


async def _run_sync(session: Session) -> tuple[int, int]:
    connector = MetaAdsConnector()
    ctx = SyncContext(
        merchant_id=DEFAULT_MERCHANT_ID,
        credential=_demo_credential(),
        row_sink=RowSink(session, DEFAULT_MERCHANT_ID, SourceSystem.META_ADS),
        http_client=httpx.AsyncClient(),
    )
    try:
        result = await connector.sync_full(ctx)
        session.commit()
    finally:
        await ctx.http_client.aclose()
    return result.rows_upserted, result.rows_skipped


async def test_meta_ads_demo_sync_writes_forty_ad_spend_rows(session: Session) -> None:
    upserted, skipped = await _run_sync(session)
    assert upserted == 40
    assert skipped == 0

    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == DEFAULT_MERCHANT_ID)
        .where(Record.source_system == SourceSystem.META_ADS.value)
    ).all()
    assert len(rows) == 40
    assert {r.entity_type for r in rows} == {EntityType.AD_SPEND.value}

    sample = rows[0]
    assert "campaign_id" in sample.normalized
    assert Decimal(sample.normalized["spend_inr"]) > Decimal("0")


async def test_meta_ads_sync_is_idempotent_via_payload_hash(session: Session) -> None:
    first_upserted, _ = await _run_sync(session)
    second_upserted, second_skipped = await _run_sync(session)

    assert first_upserted == 40
    assert second_upserted == 0
    assert second_skipped == 40

    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.META_ADS.value)
    ).all()
    assert len(rows) == 40


async def test_meta_ads_source_id_is_unique_per_campaign_day(session: Session) -> None:
    await _run_sync(session)
    rows = session.exec(
        select(Record).where(Record.source_system == SourceSystem.META_ADS.value)
    ).all()
    source_ids = [r.source_id for r in rows]
    assert len(source_ids) == len(set(source_ids))
    # Source ID encodes campaign and date — 4 campaigns x 10 days = 40 unique
    campaigns = {sid.split("_")[0] for sid in source_ids}
    assert len(campaigns) == 4
