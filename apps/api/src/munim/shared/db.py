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

DEFAULT_MERCHANT_ID = "m_default"
DEFAULT_MERCHANT_NAME = "Default Merchant"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, **_engine_kwargs(settings.database_url))


def init_db() -> None:
    """Create the universal-schema tables and seed the single-tenant merchant."""
    # Importing the models package registers every table on SQLModel.metadata.
    import munim.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _seed_default_merchant(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session


def _seed_default_merchant(engine: Engine) -> None:
    from munim.models import Merchant

    with Session(engine) as session:
        if session.get(Merchant, DEFAULT_MERCHANT_ID) is not None:
            return
        session.add(Merchant(id=DEFAULT_MERCHANT_ID, name=DEFAULT_MERCHANT_NAME))
        session.commit()


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
