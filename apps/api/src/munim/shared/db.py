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

# TEST-ONLY constant. Production code reads merchant_id from the session
# (see modules/auth/dependencies.py::get_current_merchant_id). Tests that
# don't want to round-trip through /auth/start can use this id when manually
# inserting Merchant + Record rows.
DEFAULT_MERCHANT_ID = "m_default"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = _normalize_database_url(settings.database_url)
    return create_engine(url, **_engine_kwargs(url))


def _normalize_database_url(url: str) -> str:
    # Render's PG `connectionString` property returns `postgres://...`; SQLAlchemy
    # 2.0 dropped that alias and requires `postgresql://...`. One-line rewrite.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def init_db() -> None:
    """Create the universal-schema tables. No merchant rows seeded on boot."""
    # Importing the models package registers every table on SQLModel.metadata.
    import munim.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)


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
