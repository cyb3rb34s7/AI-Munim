"""End-to-end tests for /auth/{start,me,logout}.

These tests prove the cookie round-trip: POST /auth/start sets a signed
cookie; subsequent GET /auth/me reads it; logout clears it; tampering
returns 401. The multi-merchant isolation test is the proof that the
session backbone actually keeps two visitors apart (the load-bearing
claim of Phase 9).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _session_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-for-auth-router")


def _build_client() -> TestClient:
    from munim.main import create_app

    return TestClient(create_app())


def test_start_demo_sets_cookie_and_returns_current_user() -> None:
    with _build_client() as client:
        response = client.post("/api/auth/start", json={"display_name": "Reviewer"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["display_name"] == "Reviewer"
        assert body["data"]["merchant_id"].startswith("m_")
        assert body["data"]["user_id"].startswith("u_")
        assert "munim_session" in response.cookies


def test_start_demo_with_missing_display_name_uses_default() -> None:
    with _build_client() as client:
        response = client.post("/api/auth/start", json={})
        assert response.status_code == 200
        assert response.json()["data"]["display_name"] == "Demo User"


def test_start_demo_rejects_display_name_over_max_length() -> None:
    with _build_client() as client:
        response = client.post("/api/auth/start", json={"display_name": "A" * 81})
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "validation.bad_format"


def test_me_without_cookie_returns_unauthenticated() -> None:
    with _build_client() as client:
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "auth.unauthenticated"


def test_me_after_start_returns_same_merchant() -> None:
    with _build_client() as client:
        start_body = client.post("/api/auth/start", json={"display_name": "Anita"}).json()
        me_body = client.get("/api/auth/me").json()
        assert me_body["data"]["merchant_id"] == start_body["data"]["merchant_id"]
        assert me_body["data"]["display_name"] == "Anita"


def test_logout_clears_session_then_me_returns_401() -> None:
    with _build_client() as client:
        client.post("/api/auth/start", json={}).raise_for_status()
        logout_response = client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json()["data"] == {"logged_out": True}
        me_response = client.get("/api/auth/me")
        assert me_response.status_code == 401


def test_tampered_cookie_value_returns_unauthenticated() -> None:
    with _build_client() as client:
        client.post("/api/auth/start", json={}).raise_for_status()
        original = client.cookies.get("munim_session")
        assert original is not None
        if "." in original:
            body, _sig = original.rsplit(".", 1)
            tampered = f"{body}.000000000000000000000000000"
        else:
            tampered = "garbagecookiebody"
        client.cookies.set("munim_session", tampered)
        response = client.get("/api/auth/me")
        assert response.status_code == 401


def test_cookie_issued_by_one_client_grants_identity_when_replayed_by_another() -> None:
    """The cookie IS the bearer of identity (until per-session IP/UA binding
    lands). This positive test pairs with the tampered-signature test: together
    they prove HMAC verification is the gate, not just presence-of-cookie.
    """
    with _build_client() as alpha, _build_client() as beta:
        alpha_body = alpha.post("/api/auth/start", json={"display_name": "Alpha"}).json()
        alpha_cookie = alpha.cookies.get("munim_session")
        assert alpha_cookie is not None

        beta.cookies.set("munim_session", alpha_cookie)
        me = beta.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["data"]["merchant_id"] == alpha_body["data"]["merchant_id"]


def test_two_distinct_starts_produce_distinct_merchants() -> None:
    # Two independent TestClients = two independent cookie jars =
    # two independent merchants. This is the load-bearing isolation
    # claim of Phase 9 — without it, "multi-tenant" is just a label.
    with _build_client() as a, _build_client() as b:
        body_a = a.post("/api/auth/start", json={"display_name": "Alpha"}).json()
        body_b = b.post("/api/auth/start", json={"display_name": "Beta"}).json()
        assert body_a["data"]["merchant_id"] != body_b["data"]["merchant_id"]
        assert body_a["data"]["user_id"] != body_b["data"]["user_id"]
