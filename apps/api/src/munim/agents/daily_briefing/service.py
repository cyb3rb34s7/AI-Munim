"""Service layer for the daily-briefing agent.

Owns:
  - Building a ChatContext bound to the request session + merchant.
  - Running the PydanticAI agent.
  - Collecting citations from every ToolReturnPart.
  - Running the citation enforcer on narrative + each action's reasoning.
  - Persisting a RunLog row with detail_json carrying the full briefing.

Errors:
  - LLM failures (ModelHTTPError / UnexpectedModelBehavior / httpx.HTTPError)
    become LLMUnavailableError (reusing chat.agent.LLMUnavailableError).
  - Enforcer rejection (CitationEnforcerError) propagates as-is — the
    answer was structurally dishonest; fail loudly.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits
from sqlmodel import Session
from ulid import ULID

from munim.agents.daily_briefing.agent import build_agent
from munim.agents.daily_briefing.constants import Sector
from munim.agents.daily_briefing.schemas import BriefingOutput, ProposedAction
from munim.chat.agent import LLMUnavailableError
from munim.chat.enforcer import enforce_grounded_answer
from munim.chat.tools import ChatContext
from munim.chat.types import GroundedAnswer, RowCitation, ToolResult
from munim.models import RunLog
from munim.shared.constants import AgentName, RunLogKind
from munim.shared.errors import MunimError
from munim.shared.logging import get_logger

log = get_logger("munim.agents.daily_briefing")


@dataclass
class BriefingRunSummary:
    run_id: str
    run_log_id: int
    sector: Sector
    items_scanned: int
    actions_proposed: int
    started_at: datetime
    finished_at: datetime


async def run_briefing(
    session: Session,
    merchant_id: str,
    sector: Sector,
    *,
    trace_id: str | None = None,
    model_override: Model | None = None,
) -> BriefingRunSummary:
    started_at = datetime.now(UTC)
    run_id = f"ar_{ULID()}"

    log.info(
        "agent.run.started",
        agent=AgentName.DAILY_BRIEFING.value,
        run_id=run_id,
        merchant_id=merchant_id,
        sector=sector.value,
    )

    ctx = ChatContext(merchant_id=merchant_id, session=session, trace_id=trace_id)
    agent = build_agent(sector, model=model_override)

    # Hard cap on LLM turns. With our 3 tools and a directive prompt, a
    # healthy run takes 3-6 turns. 12 leaves headroom for one re-think, but
    # cuts off the pathological "keep re-querying the same filter" loop
    # that gpt-4o-mini occasionally falls into.
    usage_limits = UsageLimits(request_limit=12)

    try:
        run_result = await agent.run(
            "Compose this week's briefing.",
            deps=ctx,
            usage_limits=usage_limits,
        )
    except MunimError:
        raise
    except UsageLimitExceeded as exc:
        log.warning(
            "agent.run.tool_loop_exhausted",
            agent=AgentName.DAILY_BRIEFING.value,
            run_id=run_id,
            exc_str=str(exc)[:200],
        )
        raise LLMUnavailableError(
            message=(
                "The model couldn't converge on a briefing within the tool-call "
                "budget. Try again."
            ),
            details={"exc_type": "UsageLimitExceeded", "exc_str": str(exc)[:500]},
        ) from exc
    except (ModelHTTPError, UnexpectedModelBehavior, httpx.HTTPError) as exc:
        log.warning(
            "agent.run.llm_unavailable",
            agent=AgentName.DAILY_BRIEFING.value,
            exc_type=type(exc).__name__,
        )
        raise LLMUnavailableError(
            message="LLM call failed.",
            details={"exc_type": type(exc).__name__, "exc_str": str(exc)[:500]},
        ) from exc

    collected: list[RowCitation] = []
    for message in run_result.all_messages():
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolReturnPart):
                content = part.content
                if isinstance(content, ToolResult):
                    collected.extend(content.citations)

    output: BriefingOutput = run_result.output

    cleaned_narrative = enforce_grounded_answer(
        GroundedAnswer(text=output.narrative, used_citations=output.used_citations),
        available_citations=collected,
    )

    cleaned_actions: list[ProposedAction] = []
    for action in output.proposed_actions:
        cleaned_reasoning = enforce_grounded_answer(
            GroundedAnswer(text=action.reasoning, used_citations=action.evidence_record_ids),
            available_citations=collected,
        )
        cleaned_actions.append(
            ProposedAction(
                action_type=action.action_type,
                reasoning=cleaned_reasoning,
                evidence_record_ids=action.evidence_record_ids,
            )
        )

    seen: set[int] = set()
    unique_citations: list[RowCitation] = []
    for c in collected:
        if c.record_id not in seen:
            unique_citations.append(c)
            seen.add(c.record_id)

    items_scanned = len(unique_citations)
    actions_proposed = len(cleaned_actions)
    finished_at = datetime.now(UTC)

    run = RunLog(
        merchant_id=merchant_id,
        kind=RunLogKind.AGENT.value,
        started_at=started_at,
        finished_at=finished_at,
        detail_json={
            "run_id": run_id,
            "agent": AgentName.DAILY_BRIEFING.value,
            "sector": sector.value,
            "orders_scanned": items_scanned,  # repurposed for the summary card
            "actions_proposed": actions_proposed,
            "decisions": [],  # briefing has no per-order decisions
            "narrative": cleaned_narrative,
            "proposed_actions": [a.model_dump() for a in cleaned_actions],
            "citations": [c.model_dump() for c in unique_citations],
            "trace_id": trace_id,
        },
    )
    session.add(run)
    session.flush()

    if run.id is None:
        raise RuntimeError(
            "RunLog.id is None after session.flush() — database autoincrement failed."
        )

    log.info(
        "agent.run.completed",
        agent=AgentName.DAILY_BRIEFING.value,
        run_id=run_id,
        merchant_id=merchant_id,
        sector=sector.value,
        items_scanned=items_scanned,
        actions_proposed=actions_proposed,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
    )

    return BriefingRunSummary(
        run_id=run_id,
        run_log_id=run.id,
        sector=sector,
        items_scanned=items_scanned,
        actions_proposed=actions_proposed,
        started_at=started_at,
        finished_at=finished_at,
    )
