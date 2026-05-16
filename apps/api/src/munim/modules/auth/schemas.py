from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StartDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=80)


class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    user_id: str
    display_name: str
    created_at: datetime
