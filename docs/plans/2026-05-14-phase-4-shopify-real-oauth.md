# Phase 4 — Shopify Real OAuth + Real Admin API Implementation Plan

> **For agentic workers:** This plan executes as **ONE subagent dispatch for the whole phase** (per `CLAUDE.md` workflow §3). Work through all 10 tasks top-to-bottom, commit per task per the plan, and report back when complete or blocked. Use `superpowers:subagent-driven-development`.
>
> **Test discipline (`docs/conventions.md §13.4`):** every test in this plan was filtered for meaningfulness. **Auth-flow code is high-risk for security bugs** — if you find yourself about to write a test that doesn't actually exercise a real failure mode (e.g., HMAC mismatch, expired state, tampered payload), don't write it. Flag it back. Conversely: if you spot a real bug class in the implementation that the plan doesn't cover, add a test for it and flag the addition.

**Goal:** Replace the demo-only `ShopifyConnector` with a real OAuth flow + real Shopify Admin API calls. After this phase, clicking "Connect to your store" on the Shopify card walks the user through real Shopify OAuth, persists an AES-GCM-encrypted access token, and "Sync now" hits the real Admin API of their dev store. The demo button stays as-is so a reviewer without credentials can still walk the README flow.

**Architecture:**
- New `shared/crypto.py` owns AES-GCM blob encryption (for `connector_credentials.auth_blob_encrypted`) and HMAC-signed OAuth state tokens (so we don't need a `oauth_state` table).
- New `modules/connectors/oauth_shopify.py` owns Shopify-specific OAuth helpers (build authorize URL, exchange code, verify Shopify's callback HMAC). Other connectors (Phase 5) will add their own `oauth_<name>.py`.
- `BaseConnector` ABC simplified: drops `authorize_url` and `exchange_code` (auth is per-provider, not via a uniform ABC — keeping them there would force a Liskov violation when one connector's auth signature differs from another's).
- Frontend gains a "Connect to your store" button on the Shopify card next to "Connect (demo)". Clicking opens a modal asking for the shop subdomain (defaults to `munim-dev`), POSTs to `/api/connectors/shopify/oauth/init`, and redirects the browser to Shopify. Shopify's callback hits our backend, which exchanges the code, stores the encrypted credential, and 302s back to `/connectors?connected=shopify`. The page reads the query param and shows a success strip.

**Tech stack additions:**
- `cryptography>=44.0` (AES-GCM + HMAC; well-maintained, MIT-licensed, ships pre-built wheels on Linux/macOS/Windows).
- `respx>=0.22` (httpx mocking for tests; lets us assert the exact Shopify request shape without hitting the network).

**Out of scope, called out:**
- Webhook ingestion (Shopify can push order events; we still poll on demand. Phase 8.).
- Token refresh (Shopify offline-mode tokens are long-lived; no refresh needed).
- Multi-store per merchant (v0 is single-tenant — one credential per `(merchant_id, connector)`).
- Connector-level multi-tenancy beyond what `merchant_id` already provides.
- Migration of EXISTING demo credentials to encrypted form (demo blobs stay plaintext JSON since `{"status": "demo", "fixture_path": ...}` carries no secret).

---

## File map

**New files:**
- `apps/api/src/munim/shared/crypto.py` — AES-GCM + state sign/verify + HMAC verify helpers.
- `apps/api/src/munim/shared/tests/__init__.py` (empty).
- `apps/api/src/munim/shared/tests/test_crypto.py` — crypto unit tests.
- `apps/api/src/munim/modules/connectors/oauth_shopify.py` — Shopify-specific OAuth helpers.
- `apps/api/src/munim/modules/connectors/tests/test_oauth_shopify.py` — OAuth helper tests.
- `apps/api/src/munim/modules/connectors/tests/test_oauth_router.py` — OAuth endpoint integration tests.
- `apps/web/src/modules/connectors/components/ShopOAuthModal.tsx` — modal asking for shop subdomain.
- `apps/web/src/modules/connectors/hooks/useStartOAuthMutation.ts` — POST `/oauth/init` then redirect.

**Modified files:**
- `apps/api/pyproject.toml` — add `cryptography` + `respx`.
- `apps/api/src/munim/shared/config.py` — add Shopify + crypto env vars (REQUIRED, no defaults).
- `apps/api/src/munim/shared/constants.py` — add `AUTH_INVALID_STATE`, `AUTH_HMAC_MISMATCH`, `AUTH_OAUTH_EXCHANGE_FAILED`, `CONNECTOR_INVALID_SHOP_DOMAIN` error codes.
- `apps/api/src/munim/connectors/base.py` — remove `authorize_url` and `exchange_code` from the ABC (OAuth is per-provider).
- `apps/api/src/munim/connectors/shopify/connector.py` — drop the `authorize_url`/`exchange_code` overrides; update `validate` to hit `/shop.json` for real credentials.
- `apps/api/src/munim/connectors/shopify/client.py` — add the real `iter_orders` path with auth header, pagination, 429 retry.
- `apps/api/src/munim/modules/connectors/schemas.py` — add `StartOAuthRequest`, `StartOAuthResponse`, `OAuthCallbackQuery`.
- `apps/api/src/munim/modules/connectors/service.py` — add `start_oauth`, `complete_oauth`; service now decrypts the credential blob before passing to the connector.
- `apps/api/src/munim/modules/connectors/router.py` — add `/oauth/init` and `/oauth/callback` endpoints.
- `apps/web/src/modules/connectors/types/connector.types.ts` — add Zod schemas for OAuth init/response.
- `apps/web/src/modules/connectors/api/connectors.api.ts` — add `postOAuthInit`.
- `apps/web/src/modules/connectors/components/ConnectorCard.tsx` — second button: "Connect to your store".
- `apps/web/src/modules/connectors/components/ConnectorsPage.tsx` — wire OAuth modal + read `?connected=shopify` query.

---

## Task 1 — Settings + crypto dep + new error codes

**Files:**
- Modify: `apps/api/pyproject.toml` — add `cryptography` and `respx`.
- Modify: `apps/api/src/munim/shared/config.py` — REQUIRED env vars for Shopify + encryption.
- Modify: `apps/api/src/munim/shared/constants.py` — new error codes.

- [ ] **Step 1: Add deps**

In `apps/api/pyproject.toml`:

```toml
dependencies = [
    "fastapi>=0.115,<0.117",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlmodel>=0.0.22",
    "structlog>=24.4",
    "python-ulid>=3.0",
    "httpx>=0.28",
    "cryptography>=44.0",
]
```

And in `[dependency-groups].dev`:

```toml
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "mypy>=1.13",
    "pre-commit>=4.0",
    "respx>=0.22",
]
```

Then from `apps/api`:
```
uv sync
```

- [ ] **Step 2: Add Shopify + crypto env vars to Settings**

In `apps/api/src/munim/shared/config.py`, extend `Settings`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Phase 1 — sensible defaults.
    database_url: str = "sqlite:///./data/munim.sqlite"
    log_level: str = "info"
    app_env: str = "development"

    # Phase 4 — Shopify OAuth + Admin API. REQUIRED at startup (no defaults).
    shopify_client_id: str
    shopify_client_secret: str
    shopify_api_version: str = "2026-04"
    shopify_oauth_redirect_uri: str
    shopify_default_shop_domain: str  # convenience default for the modal

    # AES-GCM key for encrypting connector_credentials.auth_blob_encrypted.
    # URL-safe base64; must decode to 32 bytes for AES-256-GCM.
    credentials_encryption_key: str

    # Frontend URL used by the OAuth callback redirect.
    frontend_base_url: str = "http://localhost:5173"
```

The required fields have no default — `uv run uvicorn ...` will throw `ValidationError` at startup if any of `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_OAUTH_REDIRECT_URI`, `SHOPIFY_DEFAULT_SHOP_DOMAIN`, or `CREDENTIALS_ENCRYPTION_KEY` is missing. This is the §9 fail-fast behaviour by construction — do not add `= ""` defaults.

- [ ] **Step 3: Update `.env.example`** (committed, no secret values)

Replace the commented Phase 2+ block in `apps/api/.env.example` (the file at repo root `/.env.example` is the dev-facing copy; both should be updated consistently):

```
# --- Phase 4: Shopify real OAuth (required at startup) ---
SHOPIFY_CLIENT_ID=
SHOPIFY_CLIENT_SECRET=
SHOPIFY_API_VERSION=2026-04
SHOPIFY_OAUTH_REDIRECT_URI=http://localhost:8000/api/connectors/shopify/oauth/callback
SHOPIFY_DEFAULT_SHOP_DOMAIN=your-store.myshopify.com

# AES-GCM key (URL-safe base64, decodes to 32 bytes). Generate with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
CREDENTIALS_ENCRYPTION_KEY=

# Optional — base URL the OAuth callback redirects back to (default works for dev)
FRONTEND_BASE_URL=http://localhost:5173
```

The real values are already in `apps/api/.env` (gitignored). Don't echo them anywhere.

- [ ] **Step 4: New error codes**

In `apps/api/src/munim/shared/constants.py`, extend `ErrorCode`:

```python
class ErrorCode(StrEnum):
    SYSTEM_UNEXPECTED = "system.unexpected"
    SYSTEM_DATABASE_UNAVAILABLE = "system.database_unavailable"
    VALIDATION_MISSING_FIELD = "validation.missing_field"
    VALIDATION_BAD_FORMAT = "validation.bad_format"
    CONNECTOR_NOT_CONFIGURED = "connector.not_configured"
    CONNECTOR_SYNC_FAILED = "connector.sync_failed"
    CONNECTOR_UNKNOWN = "connector.unknown"
    CONNECTOR_NOT_CONNECTED = "connector.not_connected"
    CONNECTOR_INVALID_SHOP_DOMAIN = "connector.invalid_shop_domain"
    RECORD_NOT_FOUND = "record.not_found"
    AUTH_INVALID_STATE = "auth.invalid_state"
    AUTH_HMAC_MISMATCH = "auth.hmac_mismatch"
    AUTH_OAUTH_EXCHANGE_FAILED = "auth.oauth_exchange_failed"
```

- [ ] **Step 5: Verify env loading works**

From `apps/api`:
```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
uv run python -c "from munim.shared.config import get_settings; s = get_settings(); print('shop:', s.shopify_default_shop_domain, 'api:', s.shopify_api_version)"
```
Expected: prints `shop: munim-dev.myshopify.com api: 2026-04`.

Then test the fail-fast: temporarily rename `apps/api/.env` to `.env.bak`, run the same command, expect `ValidationError`. Restore the file.

- [ ] **Step 6: Lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```
Expected: all green.

- [ ] **Step 7: Commit**

```
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/src/munim/shared/config.py apps/api/src/munim/shared/constants.py .env.example
git commit -m "feat(config): add Shopify OAuth + crypto env vars + cryptography dep"
```

---

## Task 2 — `shared/crypto.py`: AES-GCM + state sign/verify + Shopify HMAC verify

**Files:**
- Create: `apps/api/src/munim/shared/crypto.py`
- Create: `apps/api/src/munim/shared/tests/__init__.py`
- Create: `apps/api/src/munim/shared/tests/test_crypto.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/shared/tests/__init__.py` (empty).

Create `apps/api/src/munim/shared/tests/test_crypto.py`:

```python
"""Auth-critical code; every test here pins a specific failure mode."""

import base64
import hashlib
import hmac
import time
from typing import Any

import pytest

from munim.shared.crypto import (
    HMACMismatchError,
    InvalidShopDomainError,
    InvalidStateTokenError,
    decrypt_blob,
    encrypt_blob,
    sign_state,
    validate_shop_domain,
    verify_shopify_callback_hmac,
    verify_state,
)

# URL-safe base64 of 32 bytes — deterministic for tests.
TEST_KEY = base64.urlsafe_b64encode(b"\x42" * 32).rstrip(b"=").decode()


def test_encrypt_decrypt_round_trip() -> None:
    # Without this, the access-token blob written to the DB cannot be read
    # back into the connector. End-to-end break.
    plaintext = '{"status":"connected","access_token":"shpat_xxx","shop":"m.myshopify.com"}'
    ciphertext = encrypt_blob(plaintext, TEST_KEY)
    assert ciphertext != plaintext
    assert decrypt_blob(ciphertext, TEST_KEY) == plaintext


def test_decrypt_rejects_tampered_ciphertext() -> None:
    # AES-GCM is AEAD — tampering must fail authentication, not silently
    # decrypt to garbage. Without this guard, an attacker who can write to
    # the DB can substitute their own token.
    ciphertext = encrypt_blob("hello", TEST_KEY)
    tampered = ciphertext[:-4] + ("A" if ciphertext[-1] != "A" else "B") * 4
    with pytest.raises(Exception):  # cryptography.exceptions.InvalidTag
        decrypt_blob(tampered, TEST_KEY)


def test_decrypt_rejects_wrong_key() -> None:
    ciphertext = encrypt_blob("hello", TEST_KEY)
    other_key = base64.urlsafe_b64encode(b"\xff" * 32).rstrip(b"=").decode()
    with pytest.raises(Exception):
        decrypt_blob(ciphertext, other_key)


def test_sign_state_round_trip() -> None:
    payload = {"merchant_id": "m_default", "shop": "munim-dev.myshopify.com", "iat": int(time.time())}
    token = sign_state(payload, TEST_KEY)
    rebuilt = verify_state(token, TEST_KEY)
    assert rebuilt["merchant_id"] == "m_default"
    assert rebuilt["shop"] == "munim-dev.myshopify.com"


def test_verify_state_rejects_signature_tamper() -> None:
    # If we accept tampered state, an attacker can hand-craft a callback
    # that drops a credential into another merchant's row.
    payload = {"merchant_id": "m_default", "shop": "s.myshopify.com", "iat": int(time.time())}
    token = sign_state(payload, TEST_KEY)
    body, sig = token.split(".", 1)
    bad_sig = "A" * len(sig)
    with pytest.raises(InvalidStateTokenError):
        verify_state(f"{body}.{bad_sig}", TEST_KEY)


def test_verify_state_rejects_expired() -> None:
    payload = {"merchant_id": "m_default", "shop": "s.myshopify.com", "iat": int(time.time()) - 3600}
    token = sign_state(payload, TEST_KEY)
    with pytest.raises(InvalidStateTokenError, match="expired"):
        verify_state(token, TEST_KEY, max_age_sec=60)


def test_verify_state_rejects_malformed() -> None:
    with pytest.raises(InvalidStateTokenError):
        verify_state("not-a-real-token", TEST_KEY)


def test_validate_shop_domain_accepts_valid_subdomain() -> None:
    assert validate_shop_domain("munim-dev.myshopify.com") == "munim-dev.myshopify.com"


@pytest.mark.parametrize(
    "bad_value",
    [
        "munim-dev",  # missing .myshopify.com
        "https://munim-dev.myshopify.com",  # scheme leak
        "munim-dev.myshopify.com.attacker.com",  # subdomain trick
        "munim-dev.myshopify.com/path",  # path injection
        "../etc/passwd.myshopify.com",  # traversal-y
        ".myshopify.com",  # empty subdomain
    ],
)
def test_validate_shop_domain_rejects_invalid(bad_value: str) -> None:
    # Each of these is a real open-redirect / SSRF risk if accepted —
    # the shop becomes the host we POST OAuth credentials to.
    with pytest.raises(InvalidShopDomainError):
        validate_shop_domain(bad_value)


def _shopify_canonical(query: dict[str, str], secret: str) -> str:
    filtered = {k: v for k, v in query.items() if k not in ("hmac", "signature")}
    message = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def test_verify_shopify_callback_hmac_accepts_valid() -> None:
    secret = "test_secret_value"
    params: dict[str, str] = {
        "shop": "munim-dev.myshopify.com",
        "code": "abc123",
        "state": "deadbeef",
        "timestamp": "1730000000",
    }
    params["hmac"] = _shopify_canonical(params, secret)
    # Should not raise.
    verify_shopify_callback_hmac(params, secret)


def test_verify_shopify_callback_hmac_rejects_tampered() -> None:
    # Tampering means an attacker is forging the callback. Must reject.
    secret = "test_secret_value"
    params: dict[str, str] = {
        "shop": "munim-dev.myshopify.com",
        "code": "abc123",
        "state": "deadbeef",
        "timestamp": "1730000000",
    }
    params["hmac"] = _shopify_canonical(params, secret)
    params["code"] = "tampered"
    with pytest.raises(HMACMismatchError):
        verify_shopify_callback_hmac(params, secret)


def test_verify_shopify_callback_hmac_rejects_missing_hmac() -> None:
    with pytest.raises(HMACMismatchError):
        verify_shopify_callback_hmac({"shop": "x.myshopify.com"}, "secret")
```

- [ ] **Step 2: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/shared/tests/test_crypto.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `crypto.py`**

Create `apps/api/src/munim/shared/crypto.py`:

```python
"""Crypto primitives used across the auth layer.

  - encrypt_blob / decrypt_blob: AES-GCM for `connector_credentials.auth_blob_encrypted`.
  - sign_state / verify_state: HMAC-signed JSON tokens for the OAuth `state`
    param, so we don't need an `oauth_state` DB table.
  - verify_shopify_callback_hmac: validates the `hmac` query param Shopify
    signs every OAuth callback with.
  - validate_shop_domain: protects every callsite that constructs a URL
    from a user-supplied shop value.

Per docs/conventions.md §10: every failure raises a typed MunimError;
silently returning False/None on tamper would be a contract bug.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError

_SHOP_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]{0,59}\.myshopify\.com$")
_NONCE_BYTES = 12  # 96-bit nonce per AES-GCM standard


class InvalidShopDomainError(MunimError):
    code = ErrorCode.CONNECTOR_INVALID_SHOP_DOMAIN.value
    http_status = 400
    message = "Shop domain is not a valid *.myshopify.com value."


class InvalidStateTokenError(MunimError):
    code = ErrorCode.AUTH_INVALID_STATE.value
    http_status = 400
    message = "OAuth state token is invalid or expired."


class HMACMismatchError(MunimError):
    code = ErrorCode.AUTH_HMAC_MISMATCH.value
    http_status = 400
    message = "OAuth callback HMAC signature did not verify."


def validate_shop_domain(shop: str) -> str:
    if not _SHOP_PATTERN.match(shop):
        raise InvalidShopDomainError(
            message=f"Invalid shop domain {shop!r}. Expected pattern <name>.myshopify.com.",
            details={"shop": shop},
        )
    return shop


def _decode_key(key_b64: str) -> bytes:
    padding = "=" * (-len(key_b64) % 4)
    raw = base64.urlsafe_b64decode(key_b64 + padding)
    if len(raw) != 32:
        raise ValueError(
            f"CREDENTIALS_ENCRYPTION_KEY must decode to 32 bytes; got {len(raw)}."
        )
    return raw


def encrypt_blob(plaintext: str, key_b64: str) -> str:
    key = _decode_key(key_b64)
    nonce = os.urandom(_NONCE_BYTES)
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).rstrip(b"=").decode("ascii")


def decrypt_blob(token: str, key_b64: str) -> str:
    key = _decode_key(key_b64)
    padding = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(token + padding)
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    cipher = AESGCM(key)
    # cryptography raises InvalidTag on tamper / wrong key — let it propagate.
    plaintext = cipher.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def sign_state(payload: dict[str, Any], key_b64: str) -> str:
    body_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    body_b64 = base64.urlsafe_b64encode(body_json.encode("utf-8")).rstrip(b"=").decode("ascii")
    key = _decode_key(key_b64)
    sig = hmac.new(key, body_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{body_b64}.{sig_b64}"


def verify_state(
    token: str,
    key_b64: str,
    max_age_sec: int = 600,
) -> dict[str, Any]:
    parts = token.split(".", 1)
    if len(parts) != 2:
        raise InvalidStateTokenError(message="Malformed state token (no separator).")
    body_b64, given_sig_b64 = parts

    key = _decode_key(key_b64)
    expected_sig = hmac.new(key, body_b64.encode("ascii"), hashlib.sha256).digest()

    given_padding = "=" * (-len(given_sig_b64) % 4)
    try:
        given_sig = base64.urlsafe_b64decode(given_sig_b64 + given_padding)
    except Exception as exc:
        raise InvalidStateTokenError(message="State signature is not valid base64.") from exc

    if not hmac.compare_digest(expected_sig, given_sig):
        raise InvalidStateTokenError(message="State signature did not verify.")

    body_padding = "=" * (-len(body_b64) % 4)
    try:
        body_bytes = base64.urlsafe_b64decode(body_b64 + body_padding)
        payload: dict[str, Any] = json.loads(body_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidStateTokenError(message="State body is not valid JSON.") from exc

    iat = payload.get("iat")
    if not isinstance(iat, int) or time.time() - iat > max_age_sec:
        raise InvalidStateTokenError(message="State token expired.")

    return payload


def verify_shopify_callback_hmac(query: dict[str, str], client_secret: str) -> None:
    """Verify Shopify's `hmac` query param on an OAuth callback.

    Per https://shopify.dev/docs/apps/auth/oauth/getting-started, Shopify
    HMAC-SHA256-signs all callback query params except `hmac` and `signature`
    using the app's client_secret. We compute the same and compare timing-safe.
    """
    given_hex = query.get("hmac")
    if not given_hex:
        raise HMACMismatchError(message="Missing hmac param on OAuth callback.")

    filtered = {k: v for k, v in query.items() if k not in ("hmac", "signature")}
    message = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    expected_hex = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hex, given_hex):
        raise HMACMismatchError(
            message="OAuth callback HMAC did not match expected signature.",
        )
```

- [ ] **Step 4: Run tests, see all pass**

```
uv run pytest src/munim/shared/tests/test_crypto.py -v
```
Expected: 12 passed (5 enumerated + 6 parametrized invalid shop + 1 expected-fixture-shape… actual count will be around 14 once parametrize expands).

- [ ] **Step 5: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/shared/crypto.py apps/api/src/munim/shared/tests
git commit -m "feat(crypto): AES-GCM + signed-state + Shopify HMAC verify helpers"
```

---

## Task 3 — `oauth_shopify.py` helpers (build authorize URL + exchange code + HTTP)

**Files:**
- Create: `apps/api/src/munim/modules/connectors/oauth_shopify.py`
- Create: `apps/api/src/munim/modules/connectors/tests/test_oauth_shopify.py`

- [ ] **Step 1: Write the failing tests first**

Create `apps/api/src/munim/modules/connectors/tests/test_oauth_shopify.py`:

```python
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from munim.modules.connectors.oauth_shopify import (
    OAuthExchangeError,
    build_shopify_authorize_url,
    exchange_shopify_code,
)


def test_authorize_url_targets_the_correct_shop_with_scopes_and_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("SHOPIFY_OAUTH_REDIRECT_URI", "http://localhost:8000/cb")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)  # 32 bytes decoded
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    url = build_shopify_authorize_url(
        merchant_id="m_default",
        shop="munim-dev.myshopify.com",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "munim-dev.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"

    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["test_client_id"]
    assert qs["redirect_uri"] == ["http://localhost:8000/cb"]
    scope_value = qs["scope"][0]
    for required in ("read_orders", "read_customers", "read_products"):
        assert required in scope_value
    # State must round-trip through verify_state for the callback to accept it.
    from munim.shared.crypto import verify_state

    state_payload = verify_state(qs["state"][0], "A" * 43)
    assert state_payload["merchant_id"] == "m_default"
    assert state_payload["shop"] == "munim-dev.myshopify.com"


def test_authorize_url_rejects_invalid_shop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "x")
    monkeypatch.setenv("SHOPIFY_OAUTH_REDIRECT_URI", "http://localhost:8000/cb")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings
    from munim.shared.crypto import InvalidShopDomainError

    get_settings.cache_clear()
    with pytest.raises(InvalidShopDomainError):
        build_shopify_authorize_url(
            merchant_id="m_default",
            shop="evil.attacker.com",
        )


@respx.mock
async def test_exchange_code_returns_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    route = respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "shpat_realtoken",
                "scope": "read_orders,read_customers",
            },
        )
    )

    async with httpx.AsyncClient() as client:
        token = await exchange_shopify_code(
            client,
            shop="munim-dev.myshopify.com",
            code="abc123",
        )

    assert token.access_token == "shpat_realtoken"
    assert token.scopes == ["read_orders", "read_customers"]
    # Verify the request body had the expected fields (not just status 200).
    request = route.calls.last.request
    body = dict(p.split("=") for p in request.content.decode().split("&"))
    assert body["client_id"] == "test_id"
    assert body["client_secret"] == "test_secret"
    assert body["code"] == "abc123"


@respx.mock
async def test_exchange_code_raises_typed_error_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "A" * 43)
    from munim.shared.config import get_settings

    get_settings.cache_clear()

    respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(401, json={"error": "invalid_request"})
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(OAuthExchangeError) as exc_info:
            await exchange_shopify_code(
                client,
                shop="munim-dev.myshopify.com",
                code="bad",
            )
    assert exc_info.value.code == "auth.oauth_exchange_failed"
```

- [ ] **Step 2: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/modules/connectors/tests/test_oauth_shopify.py -v
```

- [ ] **Step 3: Implement `oauth_shopify.py`**

Create `apps/api/src/munim/modules/connectors/oauth_shopify.py`:

```python
"""Shopify-specific OAuth helpers.

Keeps OAuth out of the BaseConnector ABC — each provider's OAuth shape
differs enough that one uniform interface would force Liskov violations.
The router for Shopify calls into here directly; Phase 5 connectors add
their own `oauth_<name>.py`.
"""

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from munim.shared.config import get_settings
from munim.shared.constants import ErrorCode
from munim.shared.crypto import (
    sign_state,
    validate_shop_domain,
)
from munim.shared.errors import MunimError

_REQUIRED_SCOPES = "read_orders,read_customers,read_products,read_inventory"


class OAuthExchangeError(MunimError):
    code = ErrorCode.AUTH_OAUTH_EXCHANGE_FAILED.value
    http_status = 502
    message = "Shopify OAuth code exchange failed."


@dataclass(frozen=True)
class ShopifyAccessToken:
    access_token: str
    scopes: list[str]


def build_shopify_authorize_url(merchant_id: str, shop: str) -> str:
    """Return the URL the browser is redirected to to start OAuth."""
    settings = get_settings()
    validate_shop_domain(shop)

    state_payload: dict[str, Any] = {
        "merchant_id": merchant_id,
        "shop": shop,
        "iat": int(time.time()),
    }
    state = sign_state(state_payload, settings.credentials_encryption_key)

    params = urlencode(
        {
            "client_id": settings.shopify_client_id,
            "scope": _REQUIRED_SCOPES,
            "redirect_uri": settings.shopify_oauth_redirect_uri,
            "state": state,
            # `grant_options[]=per-user` would give online tokens; we want
            # offline (long-lived) so we omit it. Default is offline.
        }
    )
    return f"https://{shop}/admin/oauth/authorize?{params}"


async def exchange_shopify_code(
    client: httpx.AsyncClient,
    *,
    shop: str,
    code: str,
) -> ShopifyAccessToken:
    """POST /admin/oauth/access_token and return the access token + scopes."""
    settings = get_settings()
    validate_shop_domain(shop)

    response = await client.post(
        f"https://{shop}/admin/oauth/access_token",
        data={
            "client_id": settings.shopify_client_id,
            "client_secret": settings.shopify_client_secret,
            "code": code,
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise OAuthExchangeError(
            message=f"Shopify returned {response.status_code} during code exchange.",
            details={"status": response.status_code, "body": response.text[:500]},
        )

    body = response.json()
    access_token = body.get("access_token")
    if not isinstance(access_token, str):
        raise OAuthExchangeError(
            message="Shopify response missing access_token.",
            details={"body": body},
        )
    scope_value = body.get("scope", "")
    scopes = [s for s in scope_value.split(",") if s] if isinstance(scope_value, str) else []
    return ShopifyAccessToken(access_token=access_token, scopes=scopes)
```

- [ ] **Step 4: Run tests, see them pass**

```
uv run pytest src/munim/modules/connectors/tests/test_oauth_shopify.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/modules/connectors/oauth_shopify.py apps/api/src/munim/modules/connectors/tests/test_oauth_shopify.py
git commit -m "feat(connectors): Shopify OAuth helpers — authorize URL + code exchange"
```

---

## Task 4 — Refactor `BaseConnector`: drop `authorize_url` and `exchange_code`

**Files:**
- Modify: `apps/api/src/munim/connectors/base.py` — remove the two abstract methods.
- Modify: `apps/api/src/munim/connectors/shopify/connector.py` — remove the two stub overrides; keep `validate` and update later in Task 7.

The refactor: OAuth is per-provider, not per-shared-abstraction. Keeping these on the ABC would force every future connector to either implement them with the wrong signature or raise NotImplementedError — both are noise.

- [ ] **Step 1: Modify `BaseConnector`**

Edit `apps/api/src/munim/connectors/base.py`. Remove both abstract methods:

```python
class BaseConnector(ABC):
    """Every source-specific connector implements this contract."""

    name: ClassVar[ConnectorName]

    @abstractmethod
    async def validate(self, credential: Credential) -> bool:
        """Quick credential health check."""

    @abstractmethod
    async def sync_full(self, ctx: SyncContext) -> SyncResult:
        """Full backfill from the source."""

    async def sync_incremental(self, ctx: SyncContext) -> SyncResult:
        """Default: not implemented. Connectors override to enable."""
        raise NotImplementedError(f"{self.name.value} does not implement incremental sync yet.")
```

(Drop `authorize_url` and `exchange_code` and their imports if any.)

- [ ] **Step 2: Modify `ShopifyConnector`**

Edit `apps/api/src/munim/connectors/shopify/connector.py`. Remove the `authorize_url` and `exchange_code` methods. Keep `name`, `validate` (we'll update it to support real creds in Task 7), and `sync_full`.

- [ ] **Step 3: Run the full suite — must still pass (no behaviour change yet)**

```
uv run pytest -v
```
Expected: all green. If a test referenced the dropped methods, fix it (none should — they only ever raised NotImplementedError).

- [ ] **Step 4: Lint + typecheck**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
```

- [ ] **Step 5: Commit**

```
git add apps/api/src/munim/connectors/base.py apps/api/src/munim/connectors/shopify/connector.py
git commit -m "refactor(connectors): drop authorize_url/exchange_code from BaseConnector"
```

---

## Task 5 — `service.py`: `start_oauth` + `complete_oauth` + decrypt-on-read

**Files:**
- Modify: `apps/api/src/munim/modules/connectors/schemas.py` — add OAuth request/response shapes.
- Modify: `apps/api/src/munim/modules/connectors/service.py` — add `start_oauth` + `complete_oauth`; switch credential reads to decrypt.

- [ ] **Step 1: Add OAuth response schemas**

Append to `apps/api/src/munim/modules/connectors/schemas.py`:

```python
class StartOAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shop: str


class StartOAuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorize_url: str


class OAuthCompleteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector: ConnectorView
```

- [ ] **Step 2: Update `service.py`**

Add to `apps/api/src/munim/modules/connectors/service.py`:

```python
# (existing imports + new ones below)
import httpx

from munim.modules.connectors.oauth_shopify import (
    build_shopify_authorize_url,
    exchange_shopify_code,
)
from munim.modules.connectors.schemas import (
    OAuthCompleteResult,
    StartOAuthResponse,
)
from munim.shared.config import get_settings
from munim.shared.crypto import (
    decrypt_blob,
    encrypt_blob,
    verify_shopify_callback_hmac,
    verify_state,
)


def start_oauth(merchant_id: str, name: ConnectorName, shop: str) -> StartOAuthResponse:
    if name is not ConnectorName.SHOPIFY:
        # Only Shopify has real OAuth in Phase 4. Connectors module shouldn't
        # silently accept unsupported names — raise so the frontend gets a
        # clear typed error.
        raise NotImplementedError(
            f"Real OAuth for connector {name.value!r} is not implemented yet."
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
) -> OAuthCompleteResult:
    settings = get_settings()

    # 1. HMAC verify Shopify's callback signature (proves Shopify sent this).
    verify_shopify_callback_hmac(callback_params, settings.shopify_client_secret)

    # 2. Verify our state token (proves we initiated this flow, no replay).
    state_payload = verify_state(state, settings.credentials_encryption_key)
    if state_payload.get("merchant_id") != merchant_id:
        raise InvalidStateTokenError(
            message="State token's merchant_id does not match current session."
        )
    if state_payload.get("shop") != shop:
        raise InvalidStateTokenError(
            message="State token's shop does not match callback shop."
        )

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

    view = _build_view(session, merchant_id, name)
    return OAuthCompleteResult(connector=view)
```

Need to import `InvalidStateTokenError` from `munim.shared.crypto` (add to existing imports).

- [ ] **Step 3: Update `sync_connector` to handle BOTH demo and real credentials**

In `sync_connector`, change the credential-blob handling:

```python
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
        blob_plaintext = decrypt_blob(
            credential_row.auth_blob_encrypted,
            settings.credentials_encryption_key,
        )
        blob_dict = json.loads(blob_plaintext)

    credential = Credential(
        merchant_id=merchant_id,
        connector=name,
        blob=blob_dict,
    )

    # ... rest unchanged
```

- [ ] **Step 4: Add a test that the OAuth completion writes an encrypted credential**

Add to `apps/api/src/munim/modules/connectors/tests/test_service.py` (or new `test_oauth_service.py`):

```python
import json as _json

import httpx
import pytest
import respx
from sqlmodel import Session, select

from munim.models import ConnectorCredentials
from munim.modules.connectors.service import complete_oauth, start_oauth
from munim.shared.crypto import decrypt_blob, sign_state
from munim.shared.config import get_settings
from munim.shared.constants import ConnectorName, CredentialStatus


def test_start_oauth_returns_authorize_url_for_shopify(session: Session) -> None:
    resp = start_oauth("m_default", ConnectorName.SHOPIFY, "munim-dev.myshopify.com")
    assert resp.authorize_url.startswith("https://munim-dev.myshopify.com/admin/oauth/authorize?")


@respx.mock
async def test_complete_oauth_stores_encrypted_token(session: Session) -> None:
    settings = get_settings()
    # Mint a state we know is valid.
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": __import__("time").time().__int__(),
        },
        settings.credentials_encryption_key,
    )
    # Build the callback param dict and HMAC-sign it with the client_secret
    # so the HMAC verify step in complete_oauth accepts it.
    import hashlib as _hash
    import hmac as _hmac

    raw_params = {
        "code": "abc",
        "state": state,
        "shop": "munim-dev.myshopify.com",
        "timestamp": "1730000000",
    }
    message = "&".join(f"{k}={v}" for k, v in sorted(raw_params.items()))
    raw_params["hmac"] = _hmac.new(
        settings.shopify_client_secret.encode(),
        message.encode(),
        _hash.sha256,
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
```

- [ ] **Step 5: Run tests, see them pass**

```
uv run pytest src/munim/modules/connectors -v
```

- [ ] **Step 6: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/modules/connectors/schemas.py apps/api/src/munim/modules/connectors/service.py apps/api/src/munim/modules/connectors/tests
git commit -m "feat(connectors): start_oauth + complete_oauth + decrypt-on-read"
```

---

## Task 6 — OAuth endpoints in `router.py`

**Files:**
- Modify: `apps/api/src/munim/modules/connectors/router.py`
- Create: `apps/api/src/munim/modules/connectors/tests/test_oauth_router.py`

- [ ] **Step 1: Add endpoints**

In `apps/api/src/munim/modules/connectors/router.py`, add:

```python
from fastapi.responses import RedirectResponse
from munim.modules.connectors.schemas import StartOAuthRequest, StartOAuthResponse
from munim.modules.connectors.service import complete_oauth, start_oauth
from munim.shared.config import get_settings


@router.post(
    "/{name}/oauth/init",
    response_model=SuccessEnvelope[StartOAuthResponse],
)
def oauth_init_endpoint(
    name: str,
    body: StartOAuthRequest,
    request: Request,
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[StartOAuthResponse]:
    resolved = _resolve_name(name, registry)  # Validates name + raises UnknownConnectorError
    resp = start_oauth(DEFAULT_MERCHANT_ID, resolved, body.shop)
    return SuccessEnvelope(data=resp, trace_id=request.state.trace_id)


@router.get("/{name}/oauth/callback")
async def oauth_callback_endpoint(
    name: str,
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> RedirectResponse:
    settings = get_settings()
    resolved = _resolve_name(name, registry)

    # Forward ALL query params to complete_oauth so HMAC verification can
    # use them. Pydantic-validate individually so missing required ones
    # produce a typed error envelope.
    qp = dict(request.query_params)
    code = qp.get("code")
    state = qp.get("state")
    shop = qp.get("shop")
    if not (code and state and shop):
        # Per §10: don't silently redirect — give the user a typed envelope.
        raise ValidationFailedError(
            message="Missing required OAuth callback params (code, state, shop).",
            details={"received": list(qp.keys())},
        )

    await complete_oauth(
        session,
        DEFAULT_MERCHANT_ID,
        resolved,
        code=code,
        state=state,
        shop=shop,
        callback_params=qp,
    )
    session.commit()

    # Redirect the browser back to the frontend with a success marker.
    return RedirectResponse(
        url=f"{settings.frontend_base_url}/connectors?connected={resolved.value}",
        status_code=303,
    )
```

You may need to import `ValidationFailedError` from `munim.shared.errors`.

- [ ] **Step 2: Write the failing tests**

Create `apps/api/src/munim/modules/connectors/tests/test_oauth_router.py`:

```python
import hashlib
import hmac
import time

import httpx
import respx
from fastapi.testclient import TestClient

from munim.shared.config import get_settings
from munim.shared.crypto import sign_state


def test_oauth_init_returns_authorize_url(client: TestClient) -> None:
    response = client.post(
        "/connectors/shopify/oauth/init",
        json={"shop": "munim-dev.myshopify.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["authorize_url"].startswith(
        "https://munim-dev.myshopify.com/admin/oauth/authorize?"
    )


def test_oauth_init_rejects_invalid_shop(client: TestClient) -> None:
    response = client.post(
        "/connectors/shopify/oauth/init",
        json={"shop": "evil.attacker.com"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "connector.invalid_shop_domain"


def test_oauth_callback_missing_params_returns_typed_error(client: TestClient) -> None:
    # Per §10: missing required callback params must not redirect silently.
    response = client.get("/connectors/shopify/oauth/callback?code=abc")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation.bad_format"


@respx.mock
def test_oauth_callback_full_flow_redirects_to_frontend(client: TestClient) -> None:
    settings = get_settings()
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": int(time.time()),
        },
        settings.credentials_encryption_key,
    )
    params = {
        "code": "abc",
        "state": state,
        "shop": "munim-dev.myshopify.com",
        "timestamp": str(int(time.time())),
    }
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    params["hmac"] = hmac.new(
        settings.shopify_client_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    respx.post("https://munim-dev.myshopify.com/admin/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "shpat_x", "scope": "read_orders"})
    )

    response = client.get(
        "/connectors/shopify/oauth/callback",
        params=params,
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.endswith("/connectors?connected=shopify")


@respx.mock
def test_oauth_callback_with_bad_hmac_returns_typed_error(client: TestClient) -> None:
    settings = get_settings()
    state = sign_state(
        {
            "merchant_id": "m_default",
            "shop": "munim-dev.myshopify.com",
            "iat": int(time.time()),
        },
        settings.credentials_encryption_key,
    )
    # Note: hmac is intentionally wrong.
    response = client.get(
        "/connectors/shopify/oauth/callback",
        params={
            "code": "abc",
            "state": state,
            "shop": "munim-dev.myshopify.com",
            "timestamp": "1",
            "hmac": "deadbeef",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "auth.hmac_mismatch"
```

- [ ] **Step 3: Run tests**

```
uv run pytest src/munim/modules/connectors/tests/test_oauth_router.py -v
```

- [ ] **Step 4: Lint + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

- [ ] **Step 5: Commit**

```
git add apps/api/src/munim/modules/connectors/router.py apps/api/src/munim/modules/connectors/tests/test_oauth_router.py
git commit -m "feat(connectors): /oauth/init + /oauth/callback endpoints"
```

---

## Task 7 — Real `ShopifyClient.iter_orders` + `validate`

**Files:**
- Modify: `apps/api/src/munim/connectors/shopify/client.py`
- Modify: `apps/api/src/munim/connectors/shopify/connector.py` — `validate` real path.
- Create: `apps/api/src/munim/connectors/shopify/tests/test_client_real.py`

- [ ] **Step 1: Implement real `iter_orders` with auth, pagination, retry**

Replace the body of `apps/api/src/munim/connectors/shopify/client.py` with:

```python
"""HTTP / fixture access to Shopify Admin API.

Demo mode reads a frozen fixture (Phase 2). Real mode (Phase 4) calls the
Shopify Admin API with the merchant's access token, follows the `Link`
header for cursor pagination, and retries on 429 with the suggested
Retry-After.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from munim.connectors.base import Credential
from munim.shared.config import get_settings
from munim.shared.constants import CredentialStatus

_DEFAULT_LIMIT = 250
_MAX_RETRIES_ON_429 = 5
_DEFAULT_RETRY_AFTER_SEC = 2.0
_LINK_NEXT_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')


class ShopifyClient:
    def __init__(self, credential: Credential, http_client: httpx.AsyncClient) -> None:
        self._credential = credential
        self._http_client = http_client

    async def iter_orders(self) -> AsyncIterator[dict[str, Any]]:
        status = self._credential.blob.get("status")
        if status == CredentialStatus.DEMO.value:
            async for order in self._iter_demo_orders():
                yield order
            return
        if status == CredentialStatus.CONNECTED.value:
            async for order in self._iter_real_orders():
                yield order
            return
        raise ValueError(
            f"Unsupported credential status {status!r}; expected 'demo' or 'connected'."
        )

    async def validate_credential(self) -> bool:
        """Real-mode credential check via GET /admin/api/{ver}/shop.json."""
        settings = get_settings()
        shop = self._credential.blob["shop"]
        token = self._credential.blob["access_token"]
        url = f"https://{shop}/admin/api/{settings.shopify_api_version}/shop.json"
        response = await self._http_client.get(
            url,
            headers={"X-Shopify-Access-Token": token},
            timeout=15.0,
        )
        return response.status_code == 200

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def _iter_demo_orders(self) -> AsyncIterator[dict[str, Any]]:
        fixture_path_str = self._credential.blob.get("fixture_path")
        if not fixture_path_str:
            raise ValueError(
                "Demo credential is missing 'fixture_path' — set blob['fixture_path']."
            )
        fixture_path = Path(fixture_path_str)
        with fixture_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for order in payload["orders"]:
            yield order

    async def _iter_real_orders(self) -> AsyncIterator[dict[str, Any]]:
        settings = get_settings()
        shop = self._credential.blob["shop"]
        token = self._credential.blob["access_token"]
        base_url = f"https://{shop}/admin/api/{settings.shopify_api_version}/orders.json"
        url: str | None = f"{base_url}?limit={_DEFAULT_LIMIT}&status=any"

        while url is not None:
            response = await self._get_with_429_retry(
                url, headers={"X-Shopify-Access-Token": token}
            )
            response.raise_for_status()  # any non-2xx propagates (caught in service)
            body = response.json()
            for order in body.get("orders", []):
                yield order
            url = _next_page_url(response.headers.get("link", ""))

    async def _get_with_429_retry(
        self, url: str, *, headers: dict[str, str]
    ) -> httpx.Response:
        attempt = 0
        while True:
            response = await self._http_client.get(url, headers=headers, timeout=30.0)
            if response.status_code != 429:
                return response
            attempt += 1
            if attempt > _MAX_RETRIES_ON_429:
                return response  # let raise_for_status surface it
            retry_after_header = response.headers.get("retry-after", "")
            try:
                retry_after = float(retry_after_header)
            except ValueError:
                retry_after = _DEFAULT_RETRY_AFTER_SEC
            await asyncio.sleep(retry_after)


def _next_page_url(link_header: str) -> str | None:
    match = _LINK_NEXT_PATTERN.search(link_header)
    return match.group(1) if match else None
```

- [ ] **Step 2: Update `ShopifyConnector.validate` to support real credentials**

In `apps/api/src/munim/connectors/shopify/connector.py`:

```python
async def validate(self, credential: Credential) -> bool:
    status = credential.blob.get("status")
    if status == CredentialStatus.DEMO.value:
        return True
    if status == CredentialStatus.CONNECTED.value:
        async with httpx.AsyncClient() as http_client:
            client = ShopifyClient(credential, http_client)
            return await client.validate_credential()
    raise NotImplementedError(
        f"Credential status {status!r} is not handled in validate."
    )
```

(Add `import httpx` if not present.)

- [ ] **Step 3: Write the failing tests**

Create `apps/api/src/munim/connectors/shopify/tests/test_client_real.py`:

```python
import httpx
import pytest
import respx

from munim.connectors.base import Credential
from munim.connectors.shopify.client import ShopifyClient
from munim.shared.constants import ConnectorName


def _connected_cred() -> Credential:
    return Credential(
        merchant_id="m_default",
        connector=ConnectorName.SHOPIFY,
        blob={
            "status": "connected",
            "shop": "munim-dev.myshopify.com",
            "access_token": "shpat_test",
            "scopes": ["read_orders"],
        },
    )


@respx.mock
async def test_iter_orders_real_includes_access_token_header() -> None:
    # Real bug class: forgetting to attach the X-Shopify-Access-Token
    # would yield 401 on every page. This locks the header is set.
    route = respx.get(
        "https://munim-dev.myshopify.com/admin/api/2026-04/orders.json"
    ).mock(return_value=httpx.Response(200, json={"orders": []}))

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        async for _ in client.iter_orders():
            pass

    request = route.calls.last.request
    assert request.headers["X-Shopify-Access-Token"] == "shpat_test"


@respx.mock
async def test_iter_orders_follows_link_header_for_pagination() -> None:
    # Without pagination, anyone with >250 orders sees only the first page.
    base = "https://munim-dev.myshopify.com/admin/api/2026-04/orders.json"
    page2 = f"{base}?page_info=NEXT&limit=250"

    respx.get(base, params={"limit": "250", "status": "any"}).mock(
        return_value=httpx.Response(
            200,
            json={"orders": [{"id": 1}, {"id": 2}]},
            headers={"Link": f'<{page2}>; rel="next"'},
        )
    )
    respx.get(page2).mock(
        return_value=httpx.Response(200, json={"orders": [{"id": 3}]})
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        ids = [o["id"] async for o in client.iter_orders()]

    assert ids == [1, 2, 3]


@respx.mock
async def test_iter_orders_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    # 429 with Retry-After is the actual Shopify rate limit response; if we
    # don't retry, a hot store can't be synced at all.
    base = "https://munim-dev.myshopify.com/admin/api/2026-04/orders.json"
    route = respx.get(base, params={"limit": "250", "status": "any"}).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0.01"}, json={"errors": "throttled"}),
            httpx.Response(200, json={"orders": [{"id": 7}]}),
        ]
    )

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        ids = [o["id"] async for o in client.iter_orders()]

    assert ids == [7]
    assert route.call_count == 2


@respx.mock
async def test_validate_returns_true_when_shop_endpoint_returns_200() -> None:
    respx.get(
        "https://munim-dev.myshopify.com/admin/api/2026-04/shop.json"
    ).mock(return_value=httpx.Response(200, json={"shop": {"id": 1}}))

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        assert await client.validate_credential() is True


@respx.mock
async def test_validate_returns_false_on_401() -> None:
    # Real bug class: a revoked / wrong-shop token must NOT pass validate.
    respx.get(
        "https://munim-dev.myshopify.com/admin/api/2026-04/shop.json"
    ).mock(return_value=httpx.Response(401, json={"errors": "Invalid API key"}))

    async with httpx.AsyncClient() as http_client:
        client = ShopifyClient(_connected_cred(), http_client)
        assert await client.validate_credential() is False
```

- [ ] **Step 4: Run tests**

```
uv run pytest src/munim/connectors/shopify/tests/test_client_real.py -v
```

- [ ] **Step 5: Lint + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/connectors/shopify/client.py apps/api/src/munim/connectors/shopify/connector.py apps/api/src/munim/connectors/shopify/tests/test_client_real.py
git commit -m "feat(shopify): real Admin API client — auth + pagination + 429 retry + validate"
```

---

## Task 8 — Frontend: OAuth modal + redirect + callback URL handler

**Files:**
- Modify: `apps/web/src/modules/connectors/types/connector.types.ts`
- Modify: `apps/web/src/modules/connectors/api/connectors.api.ts`
- Create: `apps/web/src/modules/connectors/hooks/useStartOAuthMutation.ts`
- Create: `apps/web/src/modules/connectors/components/ShopOAuthModal.tsx`
- Modify: `apps/web/src/modules/connectors/components/ConnectorCard.tsx`
- Modify: `apps/web/src/modules/connectors/components/ConnectorsPage.tsx`

- [ ] **Step 1: Add OAuth Zod schemas + API method**

In `apps/web/src/modules/connectors/types/connector.types.ts`, append:

```ts
export const startOAuthResponseSchema = z.object({
  authorize_url: z.string().url(),
});

export type StartOAuthResponse = z.infer<typeof startOAuthResponseSchema>;
```

In `apps/web/src/modules/connectors/api/connectors.api.ts`, append:

```ts
import {
  startOAuthResponseSchema,
  type StartOAuthResponse,
} from '../types/connector.types';

export function postOAuthInit(
  name: ConnectorName,
  shop: string,
): Promise<ApiResponse<StartOAuthResponse>> {
  return apiPost(`/connectors/${name}/oauth/init`, startOAuthResponseSchema, {
    json: { shop },
  });
}
```

(Note: `apiPost` already passes options through to ky; `json: { shop }` is the request body.)

- [ ] **Step 2: Mutation hook**

Create `apps/web/src/modules/connectors/hooks/useStartOAuthMutation.ts`:

```ts
import { useMutation } from '@tanstack/react-query';

import { postOAuthInit } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

interface StartOAuthArgs {
  name: ConnectorName;
  shop: string;
}

export function useStartOAuthMutation() {
  return useMutation({
    mutationFn: ({ name, shop }: StartOAuthArgs) => postOAuthInit(name, shop),
  });
}
```

- [ ] **Step 3: Modal component**

Create `apps/web/src/modules/connectors/components/ShopOAuthModal.tsx`:

```tsx
import { useState, type FormEvent } from 'react';

import { Button } from '@/shared/components';

interface ShopOAuthModalProps {
  open: boolean;
  defaultShop: string;
  submitting: boolean;
  error: Error | null;
  onSubmit: (shop: string) => void;
  onClose: () => void;
}

const MYSHOPIFY_SUFFIX = '.myshopify.com';

function normalizeShopInput(value: string): string {
  // Accept "munim-dev" or "munim-dev.myshopify.com"; canonicalize to the latter.
  const trimmed = value.trim().toLowerCase();
  if (trimmed.endsWith(MYSHOPIFY_SUFFIX)) {
    return trimmed;
  }
  return `${trimmed}${MYSHOPIFY_SUFFIX}`;
}

export function ShopOAuthModal({
  open,
  defaultShop,
  submitting,
  error,
  onSubmit,
  onClose,
}: ShopOAuthModalProps) {
  const [value, setValue] = useState(defaultShop);

  if (!open) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(normalizeShopInput(value));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-fg/40"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <form
        className="w-[440px] max-w-[90vw] rounded-lg border border-border bg-bg p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h3 className="text-base font-semibold">Connect your Shopify store</h3>
        <p className="mt-1 text-sm text-muted">
          Enter your shop subdomain. You'll be redirected to Shopify to approve access.
        </p>

        <label className="mt-4 block text-xs font-medium text-muted">Shop</label>
        <div className="mt-1 flex items-center rounded-md border border-border bg-bg-subtle">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="munim-dev"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none"
            autoFocus
          />
          <span className="px-3 py-2 text-xs text-muted">.myshopify.com</span>
        </div>

        {error && (
          <p className="mt-3 text-xs text-error">
            {error.message}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Continue to Shopify
          </Button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Update `ConnectorCard` to accept an `onConnectReal` callback**

In `apps/web/src/modules/connectors/components/ConnectorCard.tsx`:

```tsx
interface ConnectorCardProps {
  view: ConnectorView;
  connecting: boolean;
  syncing: boolean;
  startingOAuth: boolean;
  onConnect: (name: ConnectorName) => void;
  onConnectReal: (name: ConnectorName) => void;
  onSync: (name: ConnectorName) => void;
}

// ... inside the component, in the buttons section:
        <div className="flex gap-2">
          {!isConnected && (
            <>
              <Button onClick={() => onConnect(view.name as ConnectorName)} loading={connecting}>
                Connect (demo)
              </Button>
              <Button
                variant="secondary"
                onClick={() => onConnectReal(view.name as ConnectorName)}
                loading={startingOAuth}
              >
                Connect to your store
              </Button>
            </>
          )}
          {isConnected && (
            <Button
              variant="secondary"
              onClick={() => onSync(view.name as ConnectorName)}
              loading={syncing}
            >
              Sync now
            </Button>
          )}
        </div>
```

Update `ConnectorsGrid` to thread the new `startingOAuth: ConnectorName | null` and `onConnectReal` props.

- [ ] **Step 5: Wire `ConnectorsPage`**

In `apps/web/src/modules/connectors/components/ConnectorsPage.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useConnectMutation } from '../hooks/useConnectMutation';
import { useConnectors } from '../hooks/useConnectors';
import { useStartOAuthMutation } from '../hooks/useStartOAuthMutation';
import { useSyncMutation } from '../hooks/useSyncMutation';
import type { ConnectorName, SyncResponse } from '../types/connector.types';
import { ConnectorsGrid } from './ConnectorsGrid';
import { ShopOAuthModal } from './ShopOAuthModal';

const DEFAULT_SHOP = 'munim-dev';

export function ConnectorsPage() {
  const { connectors, isLoading, error } = useConnectors();
  const connect = useConnectMutation();
  const sync = useSyncMutation();
  const startOAuth = useStartOAuthMutation();

  const [lastSync, setLastSync] = useState<SyncResponse | null>(null);
  const [modalForName, setModalForName] = useState<ConnectorName | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  // Show a success banner after OAuth round-trip lands us at /connectors?connected=shopify.
  const [connectedNotice, setConnectedNotice] = useState<string | null>(null);
  useEffect(() => {
    const connected = searchParams.get('connected');
    if (connected) {
      setConnectedNotice(connected);
      // Clean the URL so a refresh doesn't show the banner forever.
      const next = new URLSearchParams(searchParams);
      next.delete('connected');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleConnect = (name: ConnectorName) => {
    connect.mutate(name);
  };
  const handleConnectReal = (name: ConnectorName) => {
    setModalForName(name);
  };
  const handleOAuthSubmit = (shop: string) => {
    if (!modalForName) return;
    startOAuth.mutate(
      { name: modalForName, shop },
      {
        onSuccess: (resp) => {
          window.location.href = resp.data.authorize_url;
        },
      },
    );
  };
  const handleSync = (name: ConnectorName) => {
    sync.mutate(name, {
      onSuccess: (resp) => setLastSync(resp.data),
    });
  };

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Connectors</h2>
        <p className="mt-1 text-sm text-muted">
          Three connectors behind one abstraction. Use <em>Connect (demo)</em> to load a frozen
          fixture, or <em>Connect to your store</em> to authenticate against your real Shopify shop.
        </p>
      </section>

      {connectedNotice && (
        <div className="rounded-md border border-success/30 bg-success/10 p-4 text-sm">
          <p className="font-medium text-success">
            {connectedNotice} connected. Click <em>Sync now</em> on the card to pull your orders.
          </p>
        </div>
      )}

      <ConnectorsGrid
        connectors={connectors}
        isLoading={isLoading}
        error={error}
        connectingName={connect.isPending ? connect.variables ?? null : null}
        syncingName={sync.isPending ? sync.variables ?? null : null}
        startingOAuthName={startOAuth.isPending ? modalForName : null}
        onConnect={handleConnect}
        onConnectReal={handleConnectReal}
        onSync={handleSync}
      />

      {lastSync && (
        <div className="rounded-md border border-success/30 bg-success/10 p-4 text-sm">
          <p className="font-medium text-success">
            Sync complete: {lastSync.rows_upserted} upserted, {lastSync.rows_skipped} unchanged.
          </p>
          <p className="mt-1 text-xs text-muted">
            Open the Records tab to inspect the rows + their original Shopify payloads.
          </p>
        </div>
      )}

      <ShopOAuthModal
        open={modalForName !== null}
        defaultShop={DEFAULT_SHOP}
        submitting={startOAuth.isPending}
        error={startOAuth.error}
        onSubmit={handleOAuthSubmit}
        onClose={() => setModalForName(null)}
      />
    </div>
  );
}
```

- [ ] **Step 6: Update `ConnectorsGrid` to forward the new prop**

In `apps/web/src/modules/connectors/components/ConnectorsGrid.tsx`, add `startingOAuthName` + `onConnectReal` to the props and thread them into each `ConnectorCard`.

- [ ] **Step 7: Typecheck + lint + build**

```
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\web'
pnpm typecheck
pnpm lint
pnpm build
```
Expected: all green.

- [ ] **Step 8: Commit**

```
git add apps/web/src/modules/connectors
git commit -m "feat(web): Shopify OAuth modal + redirect + callback URL handling"
```

---

## Task 9 — Manual live smoke (subagent runs this, reports back)

**Files:** none (verification only).

- [ ] **Step 1: Boot servers**

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Start-Process -FilePath "uv" -ArgumentList "run","uvicorn","munim.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api' -RedirectStandardOutput 'D:\PROJECTS\AI-MUNIM\AI-Munim\.smoke-api.log' -WindowStyle Hidden
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-Command","cd 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\web'; pnpm dev --host 127.0.0.1 --port 5173" -RedirectStandardOutput 'D:\PROJECTS\AI-MUNIM\AI-Munim\.smoke-web.log' -WindowStyle Hidden
Start-Sleep -Seconds 10
```

- [ ] **Step 2: Confirm api responds**

```
(Invoke-WebRequest 'http://127.0.0.1:8000/health' -UseBasicParsing).StatusCode
```
Expected: `200`.

- [ ] **Step 3: Confirm OAuth init endpoint returns an authorize URL**

```
Invoke-WebRequest 'http://127.0.0.1:8000/api/connectors/shopify/oauth/init' -Method POST -ContentType 'application/json' -Body '{"shop":"munim-dev.myshopify.com"}' -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: JSON envelope with `data.authorize_url` starting with `https://munim-dev.myshopify.com/admin/oauth/authorize?`.

- [ ] **Step 4: Hand off to controller for browser-driven OAuth round-trip**

The remaining steps (open browser, click Connect to your store, complete Shopify auth, redirect back, sync, verify records) involve a real Shopify login that the subagent can't drive autonomously. Report status DONE and let the controller take over the live smoke with `agent-browser` + the user's session.

---

## Task 10 — Docs + commit

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `context.md`

- [ ] **Step 1: CHANGELOG entry** (insert at top):

```
## 2026-05-14 — Phase 4: real Shopify OAuth + Admin API

**What changed:** Replaced the Shopify connector's OAuth + Admin API stubs with the real flow. `shared/crypto.py` adds AES-GCM encryption (for the access token in `connector_credentials.auth_blob_encrypted`), HMAC-signed state tokens (so we don't need a `oauth_state` table), and Shopify-style HMAC callback verification. `modules/connectors/oauth_shopify.py` adds the Shopify-specific OAuth helpers — `build_shopify_authorize_url` and `exchange_shopify_code`. New endpoints `POST /api/connectors/shopify/oauth/init` and `GET /api/connectors/shopify/oauth/callback` close the loop with a 303 redirect back to `/connectors?connected=shopify`. `ShopifyClient.iter_orders` now has a real path with the `X-Shopify-Access-Token` header, `Link`-header cursor pagination, and 429 retry honouring `Retry-After`. Frontend gains "Connect to your store" alongside "Connect (demo)" on the Shopify card, plus a modal asking for the shop subdomain and a banner showing post-OAuth success.

**Refactor:** `BaseConnector` ABC dropped `authorize_url` and `exchange_code` — OAuth shapes vary per provider and forcing a uniform ABC would create Liskov violations. Each provider's OAuth lives in its own `oauth_<name>.py`.

**Files touched:** `apps/api/src/munim/shared/crypto.py` (+ tests), `apps/api/src/munim/modules/connectors/oauth_shopify.py` (+ tests), `apps/api/src/munim/modules/connectors/{service,router,schemas}.py`, `apps/api/src/munim/connectors/{base.py,shopify/{client,connector}.py}` (+ tests), `apps/api/src/munim/shared/{config,constants}.py`, `apps/api/pyproject.toml` (cryptography + respx), `apps/web/src/modules/connectors/{components/*,hooks/*,api/*,types/*}.ts`.

**Reverts cleanly?:** yes — drop the new files, revert the modified ones. Demo flow still works.
```

- [ ] **Step 2: `context.md`**

Update:
- **Now:** "Phase 4 complete. Real Shopify OAuth + Admin API working end-to-end against a live dev store. Demo flow preserved."
- **Done:** append "2026-05-14 — Phase 4 complete. Real OAuth + Admin API for Shopify."
- **Next:** bump Phase 5 (Meta Ads + Shiprocket) to top of the list.
- **Decisions:** append an entry on dropping `authorize_url`/`exchange_code` from BaseConnector (Liskov reason).
- **Problems & solutions:** if any new ones emerged during implementation (e.g., httpx mock surprises, Shopify redirect URI gotchas), add them.

- [ ] **Step 3: Commit**

```
git add CHANGELOG.md context.md
git commit -m "docs(phase-4): record real OAuth + Admin API completion"
```

---

## Self-review

**Spec coverage check (against the brief):**
- "≥3 proper connectors behind one shared abstraction" — Shopify is now ONE proper connector with real OAuth + real API. The abstraction proven by ShopifyConnector + ConnectorRegistry is unchanged; Phase 5 adds Meta + Shiprocket on top.
- Provenance — unchanged from Phase 3 (raw payload still byte-equal on the wire), just now sourced from real Shopify instead of fixture.
- §10 no-fallbacks — every auth failure raises a typed `MunimError` subclass. HMAC mismatch, state tamper, expired state, bad shop domain, OAuth exchange failure all have distinct error codes.

**§13.4 filter applied:** every test pins a real failure mode (HMAC tamper, state expiry, missing access token header, 429 retry, redirect URL shape). No vacuous round-trip-only tests.

**Type/name consistency:**
- `CredentialStatus.DEMO.value == "demo"` and `CredentialStatus.CONNECTED.value == "connected"` — used consistently in `_iter_demo_orders` vs `_iter_real_orders`, and in service's encrypt-on-write branch.
- `auth.invalid_state`, `auth.hmac_mismatch`, `auth.oauth_exchange_failed`, `connector.invalid_shop_domain` — added to ErrorCode + raised at the right sites.
- Frontend Zod `startOAuthResponseSchema` shape matches backend `StartOAuthResponse` Pydantic shape (single `authorize_url` field).
- `Credential.blob` shape differs by status: demo has `fixture_path`, connected has `shop` + `access_token` + `scopes`. `ShopifyClient.iter_orders` branches on `status` to pick the right path.

**Out of scope (deliberate, re-listed):** webhook ingestion, token refresh, multi-store-per-merchant, demo→real credential migration (demo blobs stay plaintext).

**Security notes (auth code is high-risk):**
- HMAC comparisons use `hmac.compare_digest` (timing-safe).
- State tokens have an `iat` + max-age check (no replay beyond 10 min).
- Shop domain validated against a strict regex before being used in any URL (prevents open-redirect / SSRF).
- Access token is AES-GCM encrypted at rest; nonce is generated per write (`os.urandom(12)`).
- Decrypt-on-read in service; never written to logs; never echoed in error envelopes.
