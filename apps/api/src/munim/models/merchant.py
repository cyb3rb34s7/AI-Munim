from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Merchant(SQLModel, table=True):
    __tablename__ = "merchant"

    id: str = Field(primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
