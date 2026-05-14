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
    payload: dict[str, Any] = {
        "merchant_id": "m_default",
        "shop": "munim-dev.myshopify.com",
        "iat": int(time.time()),
    }
    token = sign_state(payload, TEST_KEY)
    rebuilt = verify_state(token, TEST_KEY)
    assert rebuilt["merchant_id"] == "m_default"
    assert rebuilt["shop"] == "munim-dev.myshopify.com"


def test_verify_state_rejects_signature_tamper() -> None:
    # If we accept tampered state, an attacker can hand-craft a callback
    # that drops a credential into another merchant's row.
    payload: dict[str, Any] = {
        "merchant_id": "m_default",
        "shop": "s.myshopify.com",
        "iat": int(time.time()),
    }
    token = sign_state(payload, TEST_KEY)
    body, sig = token.split(".", 1)
    bad_sig = "A" * len(sig)
    with pytest.raises(InvalidStateTokenError):
        verify_state(f"{body}.{bad_sig}", TEST_KEY)


def test_verify_state_rejects_expired() -> None:
    payload: dict[str, Any] = {
        "merchant_id": "m_default",
        "shop": "s.myshopify.com",
        "iat": int(time.time()) - 3600,
    }
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
