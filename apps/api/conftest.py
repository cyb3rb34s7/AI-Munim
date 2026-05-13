"""Shared pytest fixtures for apps/api.

Per docs/conventions.md §11.4: no DB mocking. Each test gets a fresh temp
SQLite file via the autouse `_isolated_sqlite` fixture, so even tests that
build their own FastAPI app pick up an isolated DB without having to opt in.

Windows note: the engine MUST be `.dispose()`d before TemporaryDirectory tries
to remove the file, otherwise the SQLAlchemy connection still holds the file
handle and rmtree raises PermissionError.
"""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolated_sqlite(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        db_url = f"sqlite:///{db_path.as_posix()}"
        monkeypatch.setenv("DATABASE_URL", db_url)

        from munim.shared.config import get_settings
        from munim.shared.db import get_engine

        get_settings.cache_clear()
        get_engine.cache_clear()
        try:
            yield
        finally:
            # Release the SQLite file handle before TemporaryDirectory deletes it.
            get_engine().dispose()
            get_settings.cache_clear()
            get_engine.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from munim.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
