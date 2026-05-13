from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class Record(SQLModel, table=True):
    """The universal storage row. One table for every entity type across every
    source system. See docs/architecture.md §4.1.
    """

    __tablename__ = "record"
    __table_args__ = (
        UniqueConstraint("merchant_id", "source_system", "source_id", name="uq_record_natural_key"),
        Index("ix_record_merchant_entity_time", "merchant_id", "entity_type", "fetched_at"),
        Index("ix_record_source", "source_system", "source_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    source_system: str
    source_id: str
    entity_type: str
    fetched_at: datetime
    payload_hash: str
    raw: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    normalized: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
