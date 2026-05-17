"""Per-merchant demo seeding.

POST /auth/start calls `seed_new_merchant(session, merchant_id)` so every
fresh visitor lands on a pre-populated workspace: 6 Shopify orders + 40
Meta Ads insights + 50 Shiprocket shipments. Cross-connector customer
hashes line up so the agent's customer-RTO signal fires immediately on
the first run.

Seeding is idempotent: the RowSink natural key
`(merchant_id, source_system, source_id)` collapses any duplicate insert
into an update; calling this twice on the same merchant writes zero new
rows.

Every connector runs through `sync_full` so the credentials row's
`last_sync_at` is stamped — without that, a subsequent click on
"Sync now" in the UI is the user's first observation that the row was
ever populated.
"""

import json
from datetime import UTC, datetime

import httpx
from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import BaseConnector, Credential, SyncContext
from munim.connectors.meta_ads.connector import MetaAdsConnector
from munim.connectors.shiprocket.connector import ShiprocketConnector
from munim.connectors.shopify.connector import ShopifyConnector
from munim.models import ConnectorCredentials
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    SourceSystem,
)


async def seed_new_merchant(session: Session, merchant_id: str) -> None:
    await _seed_demo_connector(session, merchant_id, ConnectorName.SHOPIFY, ShopifyConnector())
    await _seed_demo_connector(session, merchant_id, ConnectorName.META_ADS, MetaAdsConnector())
    await _seed_demo_connector(
        session, merchant_id, ConnectorName.SHIPROCKET, ShiprocketConnector()
    )
    session.flush()


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
