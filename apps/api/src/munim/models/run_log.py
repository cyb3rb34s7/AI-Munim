from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RunLog(SQLModel, table=True):
    """Append-only audit row for any background activity:
    connector syncs, chat turns, agent runs.
    """

    __tablename__ = "run_log"

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: str = Field(index=True)
    kind: str
    started_at: datetime
    finished_at: datetime | None = None
    detail_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
