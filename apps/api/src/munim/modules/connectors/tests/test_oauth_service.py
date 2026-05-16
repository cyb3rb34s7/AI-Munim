import hashlib
import hmac
import json as _json
import time

import httpx
import pytest
import respx
from sqlmodel import Session, select

from munim.connectors.registry import default_registry
from munim.models import ConnectorCredentials
from munim.modules.connectors.service import (
    CredentialUnreadableError,
    FeatureDisabledError,
    complete_oauth,
    start_oauth,
    sync_connector,
)
from munim.shared.config import get_settings
from munim.shared.constants import ConnectorName, CredentialStatus
from munim.shared.crypto import decrypt_blob, sign_state


def test_start_oauth_returns_authorize_url_for_shopify(session: Session) -> None:
    resp = start_oauth("m_default", ConnectorName.SHOPIFY, "munim-dev.myshopify.com")
    assert resp.authorize_url.startswith("https://munim-dev.myshopify.com/admin/oauth/authorize?")


def test_start_oauth_rejects_when_shopify_oauth_disabled(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHOPIFY_OAUTH_ENABLED", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(FeatureDisabledError) as exc_info:
            start_oauth("m_default", ConnectorName.SHOPIFY, "munim-dev.myshopify.com")
        assert exc_info.value.code == "feature.disabled"
        assert exc_info.value.http_status == 403
    finally:
        get_settings.cache_clear()


async def test_complete_oauth_rejects_when_shopify_oauth_disabled(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHOPIFY_OAUTH_ENABLED", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(FeatureDisabledError) as exc_info:
            await complete_oauth(
                session,
                "m_default",
                ConnectorName.SHOPIFY,
                code="abc",
                state="anything",
                shop="munim-dev.myshopify.com",
                callback_params={"code": "abc"},
                registry=default_registry(),
            )
        assert exc_info.value.code == "feature.disabled"
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_complete_oauth_stores_encrypted_token(session: Session) -> None:
    settings = get_settings()
    # Mint a state we know is valid.
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": int(time.time()),
        },
        settings.credentials_encryption_key,
    )
    # Build the callback param dict and HMAC-sign it with the client_secret
    # so the HMAC verify step in complete_oauth accepts it.
    raw_params = {
        "code": "abc",
        "state": state,
        "shop": "munim-dev.myshopify.com",
        "timestamp": "1730000000",
    }
    message = "&".join(f"{k}={v}" for k, v in sorted(raw_params.items()))
    raw_params["hmac"] = hmac.new(
        settings.shopify_client_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "shpat_real", "scope": "read_orders"}
        )
    )

    await complete_oauth(
        session,
        "m_default",
        ConnectorName.SHOPIFY,
        code="abc",
        state=state,
        shop="munim-dev.myshopify.com",
        callback_params=raw_params,
        registry=default_registry(),
    )
    session.commit()

    row = session.exec(
        select(ConnectorCredentials).where(
            ConnectorCredentials.connector == ConnectorName.SHOPIFY.value
        )
    ).one()
    assert row.status == CredentialStatus.CONNECTED.value
    # The stored blob must NOT contain the plaintext token.
    assert "shpat_real" not in row.auth_blob_encrypted
    # But decrypting should give it back.
    decrypted = _json.loads(
        decrypt_blob(row.auth_blob_encrypted, settings.credentials_encryption_key)
    )
    assert decrypted["access_token"] == "shpat_real"


async def test_sync_raises_credential_unreadable_when_blob_is_corrupt(session: Session) -> None:
    # Phase 4 reviewer finding (typed-error contract): if the stored
    # auth_blob_encrypted can't be decrypted (DB tamper, key rotation, or
    # legacy garbage), the failure must surface as auth.credential_unreadable
    # — NOT system.unexpected, which the frontend's code-based branch can't
    # distinguish from a random 500. Without the typed wrap in sync_connector,
    # this test fails by raising InvalidTag up to the global handler.
    session.add(
        ConnectorCredentials(
            merchant_id="m_default",
            connector=ConnectorName.SHOPIFY.value,
            auth_blob_encrypted="this-is-not-real-aes-gcm-output",
            status=CredentialStatus.CONNECTED.value,
        )
    )
    session.commit()

    with pytest.raises(CredentialUnreadableError) as exc_info:
        await sync_connector(session, "m_default", ConnectorName.SHOPIFY, default_registry())
    assert exc_info.value.code == "auth.credential_unreadable"
