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

The Shopify rows skip the connector + client layer because they don't
need fixture-path bookkeeping — we load the fixture once here, map each
row via the canonical mapper (so customer_source_id matches the Shiprocket
join key), and write directly through the RowSink.
"""

import json
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.meta_ads.connector import MetaAdsConnector
from munim.connectors.shiprocket.connector import ShiprocketConnector
from munim.connectors.shopify.mapper import map_shopify_order_to_normalized
from munim.models import ConnectorCredentials
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    EntityType,
    SourceSystem,
)

_SHOPIFY_FIXTURE = Path(__file__).parents[2] / "connectors" / "shopify" / "fixtures" / "orders.json"


async def seed_new_merchant(session: Session, merchant_id: str) -> None:
    _seed_shopify(session, merchant_id)
    await _seed_demo_connector(session, merchant_id, ConnectorName.META_ADS, MetaAdsConnector())
    await _seed_demo_connector(
        session, merchant_id, ConnectorName.SHIPROCKET, ShiprocketConnector()
    )
    session.flush()


def _seed_shopify(session: Session, merchant_id: str) -> None:
    row_sink = RowSink(session, merchant_id, SourceSystem.SHOPIFY)
    for raw in _load_shopify_fixture():
        normalized = map_shopify_order_to_normalized(raw)
        row_sink.upsert(
            source_id=str(raw["id"]),
            entity_type=EntityType.ORDER,
            raw=raw,
            normalized=normalized,
        )
    _upsert_demo_credential(session, merchant_id, ConnectorName.SHOPIFY)


async def _seed_demo_connector(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    connector: MetaAdsConnector | ShiprocketConnector,
) -> None:
    _upsert_demo_credential(session, merchant_id, name)
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


def _upsert_demo_credential(session: Session, merchant_id: str, name: ConnectorName) -> None:
    blob = json.dumps({"status": CredentialStatus.DEMO.value})
    existing = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()
    if existing is None:
        session.add(
            ConnectorCredentials(
                merchant_id=merchant_id,
                connector=name.value,
                auth_blob_encrypted=blob,
                status=CredentialStatus.DEMO.value,
            )
        )
    else:
        existing.auth_blob_encrypted = blob
        existing.status = CredentialStatus.DEMO.value
        session.add(existing)
    session.flush()


def _load_shopify_fixture() -> list[dict[str, Any]]:
    payload = json.loads(_SHOPIFY_FIXTURE.read_text(encoding="utf-8"))
    data: list[dict[str, Any]] = payload["data"]
    return data
