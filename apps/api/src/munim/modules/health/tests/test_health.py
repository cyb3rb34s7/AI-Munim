"""Tests for the /health endpoint AND for the shared envelope/trace_id/error-handler behaviour.

We piggy-back on /health for the foundation tests because it is the only endpoint
in Phase 1. As more modules land they get their own tests; envelope behaviour
itself stays validated here.
"""

from fastapi.testclient import TestClient


def test_health_returns_success_envelope(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"] == "0.1.0"
    assert body["trace_id"].startswith("tr_")


def test_response_trace_id_matches_header(client: TestClient) -> None:
    response = client.get("/api/health")

    body_trace = response.json()["trace_id"]
    header_trace = response.headers.get("x-trace-id")
    assert header_trace == body_trace
    assert body_trace.startswith("tr_")


def test_inbound_trace_id_is_preserved(client: TestClient) -> None:
    incoming = "tr_01JABCDEFGHIJKLMNOPQRSTUVW"
    response = client.get("/api/health", headers={"X-Trace-Id": incoming})

    body = response.json()
    assert body["trace_id"] == incoming
    assert response.headers["x-trace-id"] == incoming


def test_invalid_inbound_trace_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Trace-Id": "not-a-trace-id"})

    body = response.json()
    assert body["trace_id"].startswith("tr_")
    assert body["trace_id"] != "not-a-trace-id"


def test_unhandled_exception_returns_error_envelope() -> None:
    from munim.main import create_app

    app = create_app()

    @app.get("/_test/boom")
    def _boom() -> None:
        raise RuntimeError("intentional test failure")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_test/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "system.unexpected"
    assert body["trace_id"].startswith("tr_")


def test_munim_error_returns_typed_envelope() -> None:
    from munim.main import create_app
    from munim.shared.errors import MunimError

    class TeapotError(MunimError):
        code = "test.teapot"
        http_status = 418
        message = "I'm a teapot."

    app = create_app()

    @app.get("/_test/teapot")
    def _teapot() -> None:
        raise TeapotError()

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_test/teapot")

    assert response.status_code == 418
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "test.teapot"
    assert body["error"]["message"] == "I'm a teapot."
    assert body["trace_id"].startswith("tr_")
