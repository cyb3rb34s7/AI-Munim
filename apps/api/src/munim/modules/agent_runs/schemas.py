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
    # --- Briefing-only fields. None for the rto_mitigator agent. ---
    sector: str | None = None
    narrative: str | None = None
    proposed_actions: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None


class AgentRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentRunSummary]


class TriggerAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: AgentRunSummary
