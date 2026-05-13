"""Database engine and session.

Sync SQLite for v0. The migration to Postgres at scale is configuration-level
per docs/architecture.md §10 - SQLModel speaks both, and our application code
already scopes every query by `merchant_id`.

`get_engine()` is cached so tests can clear it after patching DATABASE_URL.
"""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from munim.shared.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, **_engine_kwargs(settings.database_url))


def init_db() -> None:
    """Create tables for any SQLModel subclasses imported at startup.

    Phase 1 has no models yet; this is the seam where the universal `record`,
    `merchant`, `connector_credentials`, and `run_log` tables (architecture.md §4.1)
    are created when Phase 2 imports them.
    """
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        _ensure_sqlite_parent_dir(url)
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _ensure_sqlite_parent_dir(url: str) -> None:
    file_prefix = "sqlite:///"
    if not url.startswith(file_prefix):
        return
    path = Path(url[len(file_prefix) :])
    path.parent.mkdir(parents=True, exist_ok=True)
