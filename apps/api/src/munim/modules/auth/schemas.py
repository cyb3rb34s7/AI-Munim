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


class OnboardingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shopify_rows: int
    meta_ads_rows: int
    shiprocket_rows: int
