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
        raise ValueError(f"CREDENTIALS_ENCRYPTION_KEY must decode to 32 bytes; got {len(raw)}.")
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
