"""Connectors service. The router calls only into this module; this module
calls the registry + RowSink + connectors.base.

Demo credential blob shape:
    {"status": "demo", "fixture_path": "<absolute path to orders.json>"}.
Real credential blob shape (Phase 4):
    {"status": "connected", "shop": "<shop>", "access_token": "<token>", "scopes": [...]}.
    Stored AES-GCM-encrypted in auth_blob_encrypted; decrypted on read.
"""

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from cryptography.exceptions import InvalidTag
from sqlalchemy import func
from sqlmodel import Session, col, select

from munim.connectors._row_sink import RowSink
from munim.connectors.base import Credential, SyncContext
from munim.connectors.registry import ConnectorRegistry
from munim.models import ConnectorCredentials, Record
from munim.modules.connectors.oauth_shopify import (
    build_shopify_authorize_url,
    exchange_shopify_code,
)
from munim.modules.connectors.schemas import (
    ConnectorView,
    EntityCount,
    OAuthCompleteResult,
    StartOAuthResponse,
    SyncResponse,
)
from munim.shared.config import get_settings
from munim.shared.constants import (
    ConnectorName,
    CredentialStatus,
    ErrorCode,
    SourceSystem,
)
from munim.shared.crypto import (
    InvalidStateTokenError,
    decrypt_blob,
    encrypt_blob,
    verify_shopify_callback_hmac,
    verify_state,
)
from munim.shared.errors import MunimError

# apps/api/src/munim/modules/connectors/service.py
# -> apps/api/
_API_ROOT = Path(__file__).parents[4]


class ConnectorNotConnectedError(MunimError):
    code = ErrorCode.CONNECTOR_NOT_CONNECTED.value
    http_status = 409
    message = "Connector is not connected."


class ConnectorSyncError(MunimError):
    code = ErrorCode.CONNECTOR_SYNC_FAILED.value
    http_status = 500
    message = "Sync failed."


class FeatureDisabledError(MunimError):
    code = ErrorCode.FEATURE_DISABLED.value
    http_status = 403
    message = "This feature is disabled in the current environment."


class LegacyConnectRejectedError(MunimError):
    code = ErrorCode.CONNECTOR_NOT_DEMO.value
    http_status = 400
    message = (
        "This connector uses the demo-mode path; POST /connectors/{name}/connect-demo instead."
    )


class CredentialUnreadableError(MunimError):
    """The stored credential blob could not be decrypted or parsed.

    Surfaced by `sync_connector` when AES-GCM authentication fails (tampered
    DB row), the key has changed, or the decrypted blob is not valid JSON.
    Per Phase 4 reviewer finding — must be a typed code so the frontend can
    distinguish credential corruption from a random 500.
    """

    code = ErrorCode.AUTH_CREDENTIAL_UNREADABLE.value
    http_status = 500
    message = "Stored credential could not be decrypted."


def list_connectors(
    session: Session,
    merchant_id: str,
    registry: ConnectorRegistry,
) -> list[ConnectorView]:
    return [build_connector_view(session, merchant_id, name, registry) for name in registry.names()]


def connect_demo(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    registry: ConnectorRegistry,
) -> ConnectorView:
    """Create or update a demo credential for `name`. Idempotent.

    Phase 8 demo connectors (those with `is_demo=True`) must use the dedicated
    `/connect-demo` endpoint — they read fixtures from their own package, not
    from `data/fixtures/{name}/orders.json`. Routing them through this legacy
    helper would write a credential with a bogus fixture_path.
    """
    connector = registry.get(name)
    if connector.is_demo:
        raise LegacyConnectRejectedError(
            message=(
                f"Connector {name.value!r} is a Phase 8 demo connector; "
                f"use POST /connectors/{name.value}/connect-demo instead."
            ),
            details={"connector": name.value, "use_endpoint": "/connect-demo"},
        )
    fixture_path = _resolve_demo_fixture_path(name)
    blob = {"status": CredentialStatus.DEMO.value, "fixture_path": str(fixture_path)}

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
                auth_blob_encrypted=json.dumps(blob),
                status=CredentialStatus.DEMO.value,
            )
        )
    else:
        existing.auth_blob_encrypted = json.dumps(blob)
        existing.status = CredentialStatus.DEMO.value
        session.add(existing)
    session.flush()  # so list_connectors below sees the new row

    return build_connector_view(session, merchant_id, name, registry)


def start_oauth(merchant_id: str, name: ConnectorName, shop: str) -> StartOAuthResponse:
    if name is not ConnectorName.SHOPIFY:
        # Only Shopify has real OAuth in Phase 4. Connectors module shouldn't
        # silently accept unsupported names — raise so the frontend gets a
        # clear typed error.
        raise NotImplementedError(
            f"Real OAuth for connector {name.value!r} is not implemented yet."
        )
    if not get_settings().shopify_oauth_enabled:
        raise FeatureDisabledError(
            message="Shopify OAuth is disabled in this environment.",
            details={"feature": "shopify_oauth"},
        )
    authorize_url = build_shopify_authorize_url(merchant_id=merchant_id, shop=shop)
    return StartOAuthResponse(authorize_url=authorize_url)


async def complete_oauth(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    *,
    code: str,
    state: str,
    shop: str,
    callback_params: dict[str, str],
    registry: ConnectorRegistry,
) -> OAuthCompleteResult:
    settings = get_settings()
    if not settings.shopify_oauth_enabled:
        raise FeatureDisabledError(
            message="Shopify OAuth is disabled in this environment.",
            details={"feature": "shopify_oauth"},
        )

    # 1. HMAC verify Shopify's callback signature (proves Shopify sent this).
    verify_shopify_callback_hmac(callback_params, settings.shopify_client_secret)

    # 2. Verify our state token (proves we initiated this flow, no replay).
    state_payload = verify_state(state, settings.credentials_encryption_key)
    if state_payload.get("merchant_id") != merchant_id:
        raise InvalidStateTokenError(
            message="State token's merchant_id does not match current session."
        )
    if state_payload.get("shop") != shop:
        raise InvalidStateTokenError(message="State token's shop does not match callback shop.")

    # 3. Exchange code for access token.
    async with httpx.AsyncClient() as client:
        token = await exchange_shopify_code(client, shop=shop, code=code)

    # 4. Persist encrypted credential. Upsert on (merchant_id, connector).
    blob_plaintext = json.dumps(
        {
            "status": CredentialStatus.CONNECTED.value,
            "shop": shop,
            "access_token": token.access_token,
            "scopes": token.scopes,
        }
    )
    encrypted = encrypt_blob(blob_plaintext, settings.credentials_encryption_key)

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
                auth_blob_encrypted=encrypted,
                status=CredentialStatus.CONNECTED.value,
            )
        )
    else:
        existing.auth_blob_encrypted = encrypted
        existing.status = CredentialStatus.CONNECTED.value
        session.add(existing)
    session.flush()

    view = build_connector_view(session, merchant_id, name, registry)
    return OAuthCompleteResult(connector=view)


async def sync_connector(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    registry: ConnectorRegistry,
) -> SyncResponse:
    credential_row = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()
    if credential_row is None:
        raise ConnectorNotConnectedError(
            message=f"Connector {name.value!r} has no stored credential.",
            details={"connector": name.value},
        )

    # Demo credentials store plain JSON (no secret to protect — just a
    # fixture path). Real credentials are AES-GCM-encrypted JSON. We
    # discriminate by status; demo NEVER goes through decrypt.
    if credential_row.status == CredentialStatus.DEMO.value:
        blob_dict = json.loads(credential_row.auth_blob_encrypted)
    else:
        settings = get_settings()
        try:
            blob_plaintext = decrypt_blob(
                credential_row.auth_blob_encrypted,
                settings.credentials_encryption_key,
            )
            blob_dict = json.loads(blob_plaintext)
        except (InvalidTag, ValueError, json.JSONDecodeError) as exc:
            # Per Phase 4 reviewer finding — typed code rather than the
            # generic system.unexpected the global handler would emit.
            raise CredentialUnreadableError(
                message=(
                    f"Failed to read stored credential for {name.value!r}; "
                    "the blob is corrupted or the encryption key has changed."
                ),
                details={"connector": name.value, "exc_type": type(exc).__name__},
            ) from exc

    credential = Credential(
        merchant_id=merchant_id,
        connector=name,
        blob=blob_dict,
    )

    connector = registry.get(name)
    source_system = _connector_to_source(name)
    row_sink = RowSink(session, merchant_id, source_system)

    async with httpx.AsyncClient() as http_client:
        ctx = SyncContext(
            merchant_id=merchant_id,
            credential=credential,
            row_sink=row_sink,
            http_client=http_client,
        )
        # At this boundary, anything the connector fails on IS a sync failure.
        # Typed MunimError subclasses propagate as-is so the frontend gets the
        # specific code (e.g., connector.rate_limited later); anything else is
        # rewrapped as connector.sync_failed instead of leaking as
        # system.unexpected. NOT a silent fallback per §10: we re-raise loudly
        # with the original exception chained.
        try:
            result = await connector.sync_full(ctx)
        except MunimError:
            raise
        except Exception as exc:
            raise ConnectorSyncError(
                message=f"Sync failed for connector {name.value!r}: {exc}",
                details={"connector": name.value, "exc_type": type(exc).__name__},
            ) from exc

    credential_row.last_sync_at = datetime.now(UTC)
    session.add(credential_row)
    session.flush()

    view = build_connector_view(session, merchant_id, name, registry)
    return SyncResponse(
        rows_upserted=result.rows_upserted,
        rows_skipped=result.rows_skipped,
        started_at=result.started_at,
        finished_at=result.finished_at,
        connector=view,
    )


def build_connector_view(
    session: Session,
    merchant_id: str,
    name: ConnectorName,
    registry: ConnectorRegistry,
) -> ConnectorView:
    credential_row = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == name.value)
    ).first()

    counts = _record_counts(session, merchant_id, _connector_to_source(name))
    connector = registry.get(name)

    return ConnectorView(
        name=name,
        status=CredentialStatus(credential_row.status) if credential_row else None,
        is_demo=connector.is_demo,
        last_sync_at=credential_row.last_sync_at if credential_row else None,
        record_counts=list(counts),
    )


def _record_counts(
    session: Session, merchant_id: str, source: SourceSystem
) -> Iterable[EntityCount]:
    rows = session.exec(
        select(Record.entity_type, func.count(col(Record.id)))
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == source.value)
        .group_by(Record.entity_type)
    ).all()
    return [EntityCount(entity_type=row[0], count=row[1]) for row in rows]


def _connector_to_source(name: ConnectorName) -> SourceSystem:
    return SourceSystem(name.value)


def _resolve_demo_fixture_path(name: ConnectorName) -> Path:
    return _API_ROOT / "data" / "fixtures" / name.value / "orders.json"
