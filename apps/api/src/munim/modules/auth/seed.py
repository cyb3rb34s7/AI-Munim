"""Per-merchant demo seeding.

POST /auth/onboard calls `seed_new_merchant(session, merchant_id)` so a
fresh visitor explicitly opts into a pre-populated workspace: 6 Shopify
orders + 40 Meta Ads insights + 50 Shiprocket shipments. Cross-connector
customer hashes line up so the agent's customer-RTO signal fires
immediately on the first run.

Seeding is idempotent: the RowSink natural key
`(merchant_id, source_system, source_id)` collapses any duplicate insert
into an update; calling this twice on the same merchant writes zero new
rows. The returned `OnboardingResult` reflects the rows the merchant
OWNS (count after seed), not the upsert delta of the last call, so the
UI's "Synced N orders" line is meaningful on a repeat onboard.

Every connector runs through `sync_full` so the credentials row's
`last_sync_at` is stamped.
"""

import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import func
from sqlmodel import Session, col, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import BaseConnector, Credential, SyncContext
from munim.connectors.meta_ads.connector import MetaAdsConnector
from munim.connectors.shiprocket.connector import ShiprocketConnector
from munim.connectors.shopify.connector import ShopifyConnector
from munim.models import ConnectorCredentials, Record
from munim.modules.auth.schemas import OnboardingResult
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    SourceSystem,
)


async def seed_new_merchant(session: Session, merchant_id: str) -> OnboardingResult:
    await _seed_demo_connector(session, merchant_id, ConnectorName.SHOPIFY, ShopifyConnector())
    await _seed_demo_connector(session, merchant_id, ConnectorName.META_ADS, MetaAdsConnector())
    await _seed_demo_connector(
        session, merchant_id, ConnectorName.SHIPROCKET, ShiprocketConnector()
    )
    session.flush()
    return OnboardingResult(
        shopify_rows=_count_rows(session, merchant_id, SourceSystem.SHOPIFY),
        meta_ads_rows=_count_rows(session, merchant_id, SourceSystem.META_ADS),
        shiprocket_rows=_count_rows(session, merchant_id, SourceSystem.SHIPROCKET),
    )


async def _seed_demo_connector(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    connector: BaseConnector,
) -> None:
    credential_row = _upsert_demo_credential(session, merchant_id, name)
    source_system = SourceSystem(name.value)
    row_sink = RowSink(session, merchant_id, source_system)
    credential = Credential(
        merchant_id=merchant_id,
        connector=name,
        blob={"status": CredentialStatus.DEMO.value},
    )
    async with httpx.AsyncClient() as http_client:
        ctx = SyncContext(
            merchant_id=merchant_id,
            credential=credential,
            row_sink=row_sink,
            http_client=http_client,
        )
        await connector.sync_full(ctx)

    credential_row.last_sync_at = datetime.now(UTC)
    session.add(credential_row)
    session.flush()


def _upsert_demo_credential(
    session: Session, merchant_id: str, name: ConnectorName
) -> ConnectorCredentials:
    blob = json.dumps({"status": CredentialStatus.DEMO.value})
    existing = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()
    if existing is None:
        row = ConnectorCredentials(
            merchant_id=merchant_id,
            connector=name.value,
            auth_blob_encrypted=blob,
            status=CredentialStatus.DEMO.value,
        )
        session.add(row)
        session.flush()
        return row
    existing.auth_blob_encrypted = blob
    existing.status = CredentialStatus.DEMO.value
    session.add(existing)
    session.flush()
    return existing


def _count_rows(session: Session, merchant_id: str, source: SourceSystem) -> int:
    result = session.exec(
        select(func.count(col(Record.id)))
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == source.value)
    ).one()
    return int(result)
