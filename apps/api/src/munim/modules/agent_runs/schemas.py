from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_log_id: int
    run_id: str
    agent: str
    orders_scanned: int
    actions_proposed: int
    started_at: datetime
    finished_at: datetime


class AgentRunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_log_id: int
    run_id: str
    agent: str
    started_at: datetime
    finished_at: datetime
    orders_scanned: int
    actions_proposed: int
    decisions: list[dict[str, Any]]


class AgentRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentRunSummary]


class TriggerAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: AgentRunSummary
