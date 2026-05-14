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
