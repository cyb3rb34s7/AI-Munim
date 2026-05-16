"""Shared pytest fixtures for apps/api.

Per docs/conventions.md §11.4: no DB mocking. Each test gets a fresh temp
SQLite file via the autouse `_isolated_sqlite` fixture, so even tests that
build their own FastAPI app pick up an isolated DB without having to opt in.

Phase 9 multi-tenant note: every protected endpoint now reads merchant_id
from the session. Two test clients here:
  - `client`: anonymous TestClient. Use for /auth/start, /health, and
    cases that intentionally test the "no session -> 401" path.
  - `auth_client`: a TestClient that has already posted /auth/start so the
    signed cookie is in its jar. Returned alongside the merchant_id and
    user_id from /auth/start. Use for every protected-endpoint test.

Windows note: the engine MUST be `.dispose()`d before TemporaryDirectory tries
to remove the file, otherwise the SQLAlchemy connection still holds the file
handle and rmtree raises PermissionError.
"""

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture(autouse=True)
def _isolated_sqlite(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        db_url = f"sqlite:///{db_path.as_posix()}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("SESSION_SECRET", "test-session-secret-for-conftest")

        from munim.shared.config import get_settings
        from munim.shared.db import get_engine

        get_settings.cache_clear()
        get_engine.cache_clear()
        try:
            yield
        finally:
            get_engine().dispose()
            get_settings.cache_clear()
            get_engine.cache_clear()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Real SQLite session against the autouse temp DB."""
    from munim.shared.db import get_engine, init_db

    init_db()
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Anonymous TestClient. No session cookie. Hits unauthenticated paths only."""
    from munim.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@dataclass
class AuthClient:
    client: TestClient
    merchant_id: str
    user_id: str


@pytest.fixture
def auth_client() -> Generator[AuthClient, None, None]:
    """TestClient with a freshly minted session cookie for a new merchant."""
    from munim.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.post("/auth/start", json={"display_name": "Test User"})
        response.raise_for_status()
        body = response.json()
        yield AuthClient(
            client=test_client,
            merchant_id=body["data"]["merchant_id"],
            user_id=body["data"]["user_id"],
        )
