"""Tests for the session dependency.

The dependency is the load-bearing piece of multi-tenancy: every protected
endpoint reads merchant_id through it. These tests prove:
  - missing session -> typed 401 with `auth.unauthenticated`
  - happy path returns the merchant id from `request.session`
  - signed-cookie tampering -> 401 (proves starlette's HMAC is enforced)
"""

from collections.abc import Generator

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from munim.modules.auth.dependencies import (
    SESSION_MERCHANT_KEY,
    SESSION_USER_KEY,
    get_current_merchant_id,
)
from munim.shared.errors import install_error_handlers
from munim.shared.trace import TraceIdMiddleware

SECRET = "test-session-secret-just-for-this-file"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=SECRET, session_cookie="munim_session")
    app.add_middleware(TraceIdMiddleware)
    install_error_handlers(app)

    @app.post("/_set_session")
    def set_session(request: Request, merchant_id: str, user_id: str) -> dict[str, str]:
        request.session[SESSION_MERCHANT_KEY] = merchant_id
        request.session[SESSION_USER_KEY] = user_id
        return {"ok": "1"}

    @app.get("/_whoami")
    def whoami(merchant_id: str = Depends(get_current_merchant_id)) -> dict[str, str]:
        return {"merchant_id": merchant_id}

    return app


@pytest.fixture
def app_client() -> Generator[TestClient, None, None]:
    with TestClient(_build_app()) as test_client:
        yield test_client


def test_dependency_raises_typed_401_when_session_missing(app_client: TestClient) -> None:
    response = app_client.get("/_whoami")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "auth.unauthenticated"
    assert body["trace_id"].startswith("tr_")


def test_dependency_returns_merchant_id_when_session_set(app_client: TestClient) -> None:
    app_client.post("/_set_session?merchant_id=m_test_42&user_id=u_test_42").raise_for_status()
    response = app_client.get("/_whoami")
    assert response.status_code == 200
    assert response.json() == {"merchant_id": "m_test_42"}


def test_tampered_cookie_falls_through_to_unauthenticated(app_client: TestClient) -> None:
    app_client.post("/_set_session?merchant_id=m_real&user_id=u_real").raise_for_status()
    original = app_client.cookies.get("munim_session")
    assert original is not None
    # Flip a character mid-signature so the HMAC fails.
    flipped_char = "A" if original[-1] != "A" else "B"
    tampered = original[:-1] + flipped_char
    app_client.cookies.set("munim_session", tampered)

    response = app_client.get("/_whoami")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"
