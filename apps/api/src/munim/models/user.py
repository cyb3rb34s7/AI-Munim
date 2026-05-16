from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(primary_key=True)
    merchant_id: str = Field(foreign_key="merchant.id", index=True)
    display_name: str = "Demo User"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
