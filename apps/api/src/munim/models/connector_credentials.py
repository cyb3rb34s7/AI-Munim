from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ConnectorCredentials(SQLModel, table=True):
    """One row per (merchant, connector). Holds the credential blob.

    The blob is plain JSON in Phase 2 demo mode (no secrets to protect). When
    Phase 3 wires real OAuth, the blob is encrypted with AES-GCM using a key
    sourced from env (per docs/conventions.md §11) - column name retained.
    """

    __tablename__ = "connector_credentials"
    __table_args__ = (
        UniqueConstraint("merchant_id", "connector", name="uq_credentials_merchant_connector"),
    )

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    connector: str
    auth_blob_encrypted: str
    status: str
    last_sync_at: datetime | None = None
