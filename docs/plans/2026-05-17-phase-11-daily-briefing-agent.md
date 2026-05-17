# Phase 11 — Daily Briefing Agent (LLM-driven, sector-aware)

> **For the implementer subagent:** This plan is dispatched as a single phase. Work through it top-to-bottom, committing per task as the plan dictates. Per CLAUDE.md, also update `context.md` + `CHANGELOG.md` in the final commit. Read `docs/conventions.md` before touching code.

**Goal:** Add a second autonomous agent (`daily_briefing`) that is LLM-driven and sector-aware. It composes a 7-day plain-English briefing covering what happened, sector-specific watchouts, and 1–3 proposed actions — every numeric claim cited to a real row.

**Why second agent:** The existing `rto_mitigator` is deterministic Python (signals × weights → action). That was a deliberate auditability/cost decision (defended in `docs/architecture.md §8`). The brief said *"AI employee"*, which a reviewer might read as expecting LLM-in-the-loop. This second agent demonstrates the LLM-driven pattern alongside the deterministic one — showing breadth without removing the auditable variant.

**Architecture:** A PydanticAI agent reuses the existing `chat/tools.py` functions (`query_orders`, `query_shipments`, `query_ad_spend`) — same provenance contract, same enforcer. Sector is a per-run input from a frontend dropdown, threaded into the system prompt. The agent emits a structured `BriefingOutput { narrative, proposed_actions, used_citations }`. The narrative is post-processed by the existing citation enforcer (`chat/enforcer.py`) — any uncited number gets stripped to `[unverified number removed]`. The whole run lands in `run_log.detail_json` and renders in `RunDetailSheet` via a new branch keyed on `agent`.

**Tech Stack:** PydanticAI 1.96.0, FastAPI, SQLModel, React + TanStack Query + Tailwind.

---

## File map

**Backend (new):**
- `apps/api/src/munim/agents/daily_briefing/__init__.py`
- `apps/api/src/munim/agents/daily_briefing/constants.py` — `Sector` StrEnum + `SECTOR_HINT` map
- `apps/api/src/munim/agents/daily_briefing/schemas.py` — `BriefingOutput`, `ProposedAction`
- `apps/api/src/munim/agents/daily_briefing/agent.py` — PydanticAI Agent + sector-aware prompt builder
- `apps/api/src/munim/agents/daily_briefing/service.py` — async orchestrator: build agent → run → enforcer → persist `RunLog`
- `apps/api/src/munim/agents/daily_briefing/tests/__init__.py`
- `apps/api/src/munim/agents/daily_briefing/tests/test_schemas.py`
- `apps/api/src/munim/agents/daily_briefing/tests/test_service.py` (uses pydantic-ai TestModel — no real LLM)

**Backend (modify):**
- `apps/api/src/munim/shared/constants.py` — add `AgentName.DAILY_BRIEFING`
- `apps/api/src/munim/modules/agent_runs/router.py` — endpoint stays `POST /agents/{name}/run`; accept optional `sector` query param; for `daily_briefing` require it
- `apps/api/src/munim/modules/agent_runs/service.py` — switch to per-agent dispatch (`trigger_agent` already dispatches on name; we add the briefing class path)
- `apps/api/src/munim/modules/agent_runs/schemas.py` — extend `AgentRunDetail` with optional `narrative`, `proposed_actions`, `sector`; relax `decisions` to `list[dict] | None`

**Frontend (new):**
- `apps/web/src/shared/constants/sectors.ts` — `Sector` + `SECTOR_LABEL`
- `apps/web/src/modules/agent_runs/components/BriefingDetail.tsx` — narrative (with cited-text rendering) + proposed actions list
- `apps/web/src/modules/chat/components/CitedText.tsx` — extracted from `MessageBubble`'s renderAssistantText so both surfaces share one parser
- `apps/web/src/modules/agent_runs/components/RunBriefingButton.tsx` — sector dropdown + "Run daily briefing" button

**Frontend (modify):**
- `apps/web/src/shared/constants/agents.ts` — add `DAILY_BRIEFING` + label
- `apps/web/src/modules/agent_runs/api/client.ts` — extend `agentRunDetailSchema` with optional briefing fields; add `triggerDailyBriefing(sector)`
- `apps/web/src/modules/agent_runs/AgentRunsPage.tsx` — header gets both trigger buttons side-by-side
- `apps/web/src/modules/agent_runs/components/RunDetailSheet.tsx` — branch on `data.agent` → existing decisions UI OR new `BriefingDetail`
- `apps/web/src/modules/chat/components/MessageBubble.tsx` — refactor to use `CitedText` (no behavior change)
- `apps/web/src/modules/agent_runs/hooks/useTriggerAgent.ts` — generalize toast description so briefing summary doesn't say "0 orders scanned" when it actually did scan

---

## Tasks

### Task 1 — Backend constants + schemas

**Files:**
- Modify: `apps/api/src/munim/shared/constants.py`
- Create: `apps/api/src/munim/agents/daily_briefing/__init__.py` (empty)
- Create: `apps/api/src/munim/agents/daily_briefing/constants.py`
- Create: `apps/api/src/munim/agents/daily_briefing/schemas.py`
- Create: `apps/api/src/munim/agents/daily_briefing/tests/__init__.py` (empty)
- Create: `apps/api/src/munim/agents/daily_briefing/tests/test_schemas.py`

- [ ] **Step 1.1: Add `AgentName.DAILY_BRIEFING` to `apps/api/src/munim/shared/constants.py`**

In the `AgentName` StrEnum, add the new variant:

```python
class AgentName(StrEnum):
    RTO_MITIGATOR = "rto_mitigator"
    DAILY_BRIEFING = "daily_briefing"
```

- [ ] **Step 1.2: Create `daily_briefing/constants.py` with `Sector` enum + sector hints**

```python
"""Sector taxonomy for the daily-briefing agent.

The sector is per-run (chosen from a frontend dropdown), not stored on
the merchant — we want stateless multi-tenant demo experience. The hint
maps to a sentence the agent splices into its system prompt to bias the
narrative toward sector-specific concerns.
"""

from enum import StrEnum


class Sector(StrEnum):
    FASHION = "fashion"
    BEAUTY = "beauty"
    FMCG = "fmcg"
    ELECTRONICS = "electronics"
    HOME = "home"
    GENERIC = "generic"


SECTOR_HINT: dict[Sector, str] = {
    Sector.FASHION: (
        "Watch for high return/RTO rates (size and fit issues), seasonal "
        "demand windows, and repeat-RTO customers who keep ordering COD."
    ),
    Sector.BEAUTY: (
        "Watch for repurchase windows (30-60 day SKU lifecycle), review-driven "
        "Meta campaigns, and low-AOV bundling opportunities."
    ),
    Sector.FMCG: (
        "Watch for cart-size optimisation, repeat-customer retention, and "
        "low-margin order cancellation risk."
    ),
    Sector.ELECTRONICS: (
        "Watch for high-AOV COD risk (an RTO loses thousands per order), "
        "warranty-driven retention, and fraud signals on first-time buyers."
    ),
    Sector.HOME: (
        "Watch for heavy/oversize logistics cost, slow delivery zones, and "
        "low repurchase frequency."
    ),
    Sector.GENERIC: (
        "Watch for RTO patterns, ad-spend efficiency, and customer "
        "concentration risk."
    ),
}
```

- [ ] **Step 1.3: Create `daily_briefing/schemas.py`**

```python
"""Structured output for the daily-briefing LLM agent.

`BriefingOutput.narrative` carries inline `[cite:N,...]` markers — the
same contract as `chat.types.GroundedAnswer.text`. The existing
`chat.enforcer.enforce_grounded_answer` post-processor consumes it.

`proposed_actions` is a separate list (1-3 items). Each action has its
own short reasoning string; the reasoning ALSO follows the citation
contract so the operator can hover and see the source row.
"""

from pydantic import BaseModel, ConfigDict, Field


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str = Field(
        description="Plain-English action title, e.g. 'Convert COD order to prepaid'."
    )
    reasoning: str = Field(
        description=(
            "1-2 sentences explaining why. Every numeric claim must carry a "
            "[cite:row_id] marker referencing a row from the tools."
        )
    )
    evidence_record_ids: list[int] = Field(
        default_factory=list,
        description="Row ids that justify this action.",
    )


class BriefingOutput(BaseModel):
    # NOTE: extra="forbid" omitted by design — PydanticAI's structured-output
    # JSON schema serialisation can inject bookkeeping fields. Same exception
    # as `chat.types.GroundedAnswer`.

    narrative: str = Field(
        description=(
            "4-6 sentences covering what happened over the last 7 days. "
            "Every numeric claim carries an inline [cite:row_id] marker."
        )
    )
    proposed_actions: list[ProposedAction] = Field(
        default_factory=list,
        description="1-3 concrete actions. May be empty if nothing needs intervention.",
    )
    used_citations: list[int] = Field(
        default_factory=list,
        description="Union of every row_id cited in narrative or proposed_actions.",
    )
```

- [ ] **Step 1.4: Add a unit test for the schema**

`apps/api/src/munim/agents/daily_briefing/tests/test_schemas.py`:

```python
from munim.agents.daily_briefing.schemas import BriefingOutput, ProposedAction


def test_briefing_output_roundtrip():
    out = BriefingOutput(
        narrative="You had 3 orders[cite:1,2,3] worth Rs.12,000[cite:1,2,3].",
        proposed_actions=[
            ProposedAction(
                action_type="Convert COD order to prepaid",
                reasoning="Customer #C001 has returned 3 of 5 prior shipments[cite:5].",
                evidence_record_ids=[5],
            )
        ],
        used_citations=[1, 2, 3, 5],
    )
    payload = out.model_dump()
    assert payload["narrative"].startswith("You had 3 orders")
    assert payload["proposed_actions"][0]["evidence_record_ids"] == [5]


def test_briefing_output_empty_actions_allowed():
    out = BriefingOutput(
        narrative="Quiet week — only Rs.500[cite:1] in spend.",
        used_citations=[1],
    )
    assert out.proposed_actions == []
```

Run: `uv run pytest src/munim/agents/daily_briefing/tests/test_schemas.py -v`
Expected: 2 passed.

- [ ] **Step 1.5: Commit**

```bash
git add apps/api/src/munim/shared/constants.py apps/api/src/munim/agents/daily_briefing/
git commit -m "feat(briefing): add Sector + BriefingOutput schemas for the daily-briefing agent"
```

---

### Task 2 — Backend agent + service

**Files:**
- Create: `apps/api/src/munim/agents/daily_briefing/agent.py`
- Create: `apps/api/src/munim/agents/daily_briefing/service.py`
- Create: `apps/api/src/munim/agents/daily_briefing/tests/test_service.py`

- [ ] **Step 2.1: Create `agent.py`**

```python
"""LLM-driven daily-briefing agent.

Reuses the chat tools (`query_orders`, `query_shipments`, `query_ad_spend`)
via PydanticAI tool registration. Sector is splicd into the system prompt
when the agent is built — one Agent instance per (request, sector) pair.

The agent's structured output is `BriefingOutput`. The service then runs
the citation enforcer against the narrative (and each action's reasoning)
using the union of citations returned by the tools, exactly like the chat
flow.
"""

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from munim.agents.daily_briefing.constants import SECTOR_HINT, Sector
from munim.agents.daily_briefing.schemas import BriefingOutput
from munim.chat.tools import ChatContext, query_ad_spend, query_orders, query_shipments
from munim.chat.types import ToolResult
from munim.shared.config import get_settings
from munim.shared.constants import FulfillmentStatus, PaymentMethod

_SYSTEM_PROMPT_TEMPLATE = """You are the daily-briefing AI employee for an Indian D2C brand on Shopify, Meta Ads, and Shiprocket. Sector: {sector_label}.

Your job: compose a 7-day weekly briefing that an owner can read in under a minute. Output a BriefingOutput with:
- narrative: 4-6 sentences. Cover what happened, what's notable, what's concerning. Plain English, no jargon.
- proposed_actions: 0-3 concrete actions the owner should take. Each has a short reasoning string and evidence_record_ids.
- used_citations: union of every row_id cited in narrative or proposed_actions.

SECTOR FOCUS: {sector_hint}

CITATION CONTRACT (non-negotiable):
- Every numerical value in `narrative` AND in each action's `reasoning` MUST be immediately followed by `[cite:row_id]` or `[cite:row_id,row_id,...]`, where each row_id is taken from the citations of a tool result you used.
- DERIVED COUNTS NEED CITATIONS TOO. "3 orders[cite:1,2,3]" — cite all 3 rows that produced the count.
- If you genuinely don't have a citation for a number, DO NOT state it. Say "a few" or "several" instead, or omit the count.

WORKFLOW:
1. Call query_orders to see recent orders (no filters first, scan everything).
2. Call query_shipments to understand RTO/delivery outcomes — especially for customers with multiple orders.
3. Call query_ad_spend to see marketing spend and attributed purchases.
4. Cross-reference: find customers with high RTO history, campaigns with weak ROAS, COD orders to flagged pincodes.
5. Compose the narrative + 0-3 specific, evidence-backed actions.

STYLE:
- Open with the period: "This week..." or "Over the last 7 days...".
- Name specific factors when proposing actions (the customer's prior return rate, the pincode, the campaign name).
- Use Indian rupee formatting: "Rs.2,500" or "₹2,500".
- Don't hedge. State what the data shows.
"""


_SECTOR_LABEL_FALLBACK: dict[Sector, str] = {
    Sector.FASHION: "Fashion & Apparel",
    Sector.BEAUTY: "Beauty & Cosmetics",
    Sector.FMCG: "FMCG / Consumables",
    Sector.ELECTRONICS: "Electronics & Gadgets",
    Sector.HOME: "Home & Lifestyle",
    Sector.GENERIC: "Generic D2C",
}


def build_agent(
    sector: Sector,
    model: Model | str | None = None,
) -> Agent[ChatContext, BriefingOutput]:
    settings = get_settings()
    model_spec: Model | str = model if model is not None else f"openai:{settings.openai_chat_model}"

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        sector_label=_SECTOR_LABEL_FALLBACK[sector],
        sector_hint=SECTOR_HINT[sector],
    )

    agent: Agent[ChatContext, BriefingOutput] = Agent(
        model=model_spec,
        deps_type=ChatContext,
        output_type=BriefingOutput,
        system_prompt=system_prompt,
        model_settings={"temperature": settings.openai_chat_temperature},
    )

    @agent.tool
    def _query_orders(
        run_ctx: RunContext[ChatContext],
        payment_method: PaymentMethod | None = None,
        pincode: str | None = None,
        utm_campaign: str | None = None,
        financial_status: str | None = None,
    ) -> ToolResult[list[dict[str, Any]]]:
        return query_orders(
            run_ctx.deps,
            payment_method=payment_method,
            pincode=pincode,
            utm_campaign=utm_campaign,
            financial_status=financial_status,
        )

    @agent.tool
    def _query_shipments(
        run_ctx: RunContext[ChatContext],
        customer_source_id: str | None = None,
        fulfillment_status: FulfillmentStatus | None = None,
        pincode: str | None = None,
    ) -> ToolResult[list[dict[str, Any]]]:
        return query_shipments(
            run_ctx.deps,
            customer_source_id=customer_source_id,
            fulfillment_status=fulfillment_status,
            pincode=pincode,
        )

    @agent.tool
    def _query_ad_spend(
        run_ctx: RunContext[ChatContext],
        campaign_name: str | None = None,
    ) -> ToolResult[list[dict[str, Any]]]:
        return query_ad_spend(run_ctx.deps, campaign_name=campaign_name)

    return agent
```

- [ ] **Step 2.2: Create `service.py` (the orchestrator + persistence)**

```python
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
from typing import Any

import httpx
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models import Model
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

    try:
        run_result = await agent.run("Compose this week's briefing.", deps=ctx)
    except MunimError:
        raise
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


_BRIEFING_RUN_SUMMARY_EXPORT: Any = BriefingRunSummary
```

- [ ] **Step 2.3: Create `test_service.py` using pydantic-ai's `TestModel`**

The pydantic-ai `TestModel` returns a deterministic structured output without hitting OpenAI. We seed the DB with a few records, run the briefing, and assert it persists a `RunLog` with the expected shape.

Look at `apps/api/src/munim/chat/tests/test_agent.py` for the existing TestModel pattern in this repo and follow it. If `TestModel` returns a value that doesn't satisfy our citation contract (the enforcer will strip uncited numbers), that's fine — the test asserts the structure of the persisted run, not the narrative content.

Minimum coverage:
- One test seeds 2 order records, runs the briefing for `Sector.FASHION`, and asserts:
  - one RunLog was created with kind=AGENT and agent=daily_briefing
  - `detail_json["sector"] == "fashion"`
  - `detail_json["narrative"]` is a non-empty string
  - `detail_json["proposed_actions"]` is a list
  - `detail_json["citations"]` is a list

Use a SQLite in-memory session (helper exists somewhere — search `apps/api/src/munim/agents/rto_mitigator/tests/test_agent.py` for the pattern).

Run: `uv run pytest src/munim/agents/daily_briefing/ -v`
Expected: all tests pass.

- [ ] **Step 2.4: Commit**

```bash
git add apps/api/src/munim/agents/daily_briefing/
git commit -m "feat(briefing): add LLM-driven daily-briefing agent + service"
```

---

### Task 3 — Wire briefing into the trigger endpoint

**Files:**
- Modify: `apps/api/src/munim/modules/agent_runs/router.py`
- Modify: `apps/api/src/munim/modules/agent_runs/service.py`
- Modify: `apps/api/src/munim/modules/agent_runs/schemas.py`

- [ ] **Step 3.1: Extend `AgentRunDetail` schema with briefing-shaped fields**

In `apps/api/src/munim/modules/agent_runs/schemas.py`:

```python
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
    # --- Briefing-only fields. Empty/None for the rto_mitigator agent. ---
    sector: str | None = None
    narrative: str | None = None
    proposed_actions: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None
```

- [ ] **Step 3.2: Update `service.get_agent_run` to populate the new fields**

In `apps/api/src/munim/modules/agent_runs/service.py`, `get_agent_run` reads from `row.detail_json`. Pull the new fields out:

```python
def get_agent_run(session: Session, merchant_id: str, run_log_id: int) -> AgentRunDetail:
    row = session.exec(
        select(RunLog)
        .where(RunLog.id == run_log_id)
        .where(RunLog.merchant_id == merchant_id)
        .where(RunLog.kind == RunLogKind.AGENT.value)
    ).first()
    if row is None:
        raise AgentRunNotFoundError(
            message=f"Agent run {run_log_id} not found.",
            details={"run_log_id": run_log_id},
        )
    detail = row.detail_json
    return AgentRunDetail(
        run_log_id=row.id if row.id is not None else 0,
        run_id=detail["run_id"],
        agent=detail["agent"],
        started_at=row.started_at,
        finished_at=row.finished_at if row.finished_at else row.started_at,
        orders_scanned=detail["orders_scanned"],
        actions_proposed=detail["actions_proposed"],
        decisions=detail.get("decisions", []),
        sector=detail.get("sector"),
        narrative=detail.get("narrative"),
        proposed_actions=detail.get("proposed_actions"),
        citations=detail.get("citations"),
    )
```

- [ ] **Step 3.3: Update `trigger_agent` to dispatch briefing**

In `apps/api/src/munim/modules/agent_runs/service.py`, extend the dispatch:

```python
import asyncio

from munim.agents.daily_briefing.constants import Sector as BriefingSector
from munim.agents.daily_briefing.service import run_briefing


class SectorRequiredError(MunimError):
    code = ErrorCode.VALIDATION_MISSING_FIELD.value
    http_status = 400
    message = "sector is required for the daily-briefing agent."


def trigger_agent(
    session: Session,
    merchant_id: str,
    agent_name: AgentName,
    *,
    sector: str | None = None,
    trace_id: str | None = None,
) -> TriggerAgentResponse:
    if agent_name is AgentName.DAILY_BRIEFING:
        if sector is None:
            raise SectorRequiredError(
                message="sector is required for the daily-briefing agent.",
                details={"agent": agent_name.value},
            )
        try:
            sector_enum = BriefingSector(sector)
        except ValueError as exc:
            raise SectorRequiredError(
                message=f"Unknown sector {sector!r}.",
                details={"sector": sector, "valid": [s.value for s in BriefingSector]},
            ) from exc
        try:
            summary = asyncio.run(
                run_briefing(session, merchant_id, sector_enum, trace_id=trace_id)
            )
        except MunimError:
            raise
        return TriggerAgentResponse(
            run=AgentRunSummary(
                run_log_id=summary.run_log_id,
                run_id=summary.run_id,
                agent=agent_name.value,
                orders_scanned=summary.items_scanned,
                actions_proposed=summary.actions_proposed,
                started_at=summary.started_at,
                finished_at=summary.finished_at,
            )
        )

    # Existing RTO path unchanged below this point.
    agent_cls = _AGENTS.get(agent_name)
    if agent_cls is None:
        raise AgentUnknownError(...)
    ...
```

NOTE on `asyncio.run`: FastAPI is async-native, so the cleanest fix is to make `trigger_agent` async and have the router `await` it. Make the change — convert `trigger_agent` to `async def trigger_agent(...)`, await `run_briefing` directly, and update the router endpoint to `async def trigger_agent_endpoint(...)` and `await trigger_agent(...)`. The RTO path stays sync (no `await`); wrap its existing call as-is — synchronous code is valid inside an async function.

- [ ] **Step 3.4: Update the router endpoint to accept `?sector=` query param**

In `apps/api/src/munim/modules/agent_runs/router.py`:

```python
@router.post(
    "/agents/{name}/run",
    response_model=SuccessEnvelope[TriggerAgentResponse],
)
async def trigger_agent_endpoint(
    name: str,
    request: Request,
    sector: str | None = Query(default=None),
    merchant_id: str = Depends(get_current_merchant_id),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[TriggerAgentResponse]:
    try:
        agent_name = AgentName(name)
    except ValueError as exc:
        raise AgentUnknownError(
            message=f"Agent {name!r} is not registered.",
            details={"agent": name},
        ) from exc
    result = await trigger_agent(
        session,
        merchant_id,
        agent_name,
        sector=sector,
        trace_id=request.state.trace_id,
    )
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)
```

- [ ] **Step 3.5: Run tests**

```bash
cd apps/api
uv run pytest src/munim/agents/ src/munim/modules/agent_runs/ -v
```

Expected: all pass. If existing agent_runs tests break because `trigger_agent` is now async, update them — wrap the sync call in `asyncio.run` or convert the tests to `async def` with `pytest.mark.asyncio` (look at chat tests for the pattern in this repo).

- [ ] **Step 3.6: Commit**

```bash
git add apps/api/src/munim/modules/agent_runs/
git commit -m "feat(briefing): wire daily-briefing agent into POST /agents/{name}/run with ?sector"
```

---

### Task 4 — Frontend sector constants + agent label

**Files:**
- Create: `apps/web/src/shared/constants/sectors.ts`
- Modify: `apps/web/src/shared/constants/agents.ts`

- [ ] **Step 4.1: Create `sectors.ts`**

```ts
export const Sector = {
  FASHION: 'fashion',
  BEAUTY: 'beauty',
  FMCG: 'fmcg',
  ELECTRONICS: 'electronics',
  HOME: 'home',
  GENERIC: 'generic',
} as const;
export type Sector = (typeof Sector)[keyof typeof Sector];

export const SECTOR_LABEL: Record<Sector, string> = {
  fashion: 'Fashion & Apparel',
  beauty: 'Beauty & Cosmetics',
  fmcg: 'FMCG / Consumables',
  electronics: 'Electronics & Gadgets',
  home: 'Home & Lifestyle',
  generic: 'Generic D2C',
};

export const SECTOR_OPTIONS: Sector[] = [
  Sector.FASHION,
  Sector.BEAUTY,
  Sector.FMCG,
  Sector.ELECTRONICS,
  Sector.HOME,
  Sector.GENERIC,
];
```

- [ ] **Step 4.2: Extend `agents.ts`**

```ts
export const AgentName = {
  RTO_MITIGATOR: 'rto_mitigator',
  DAILY_BRIEFING: 'daily_briefing',
} as const;
export type AgentName = (typeof AgentName)[keyof typeof AgentName];

const AGENT_LABEL: Record<AgentName, string> = {
  [AgentName.RTO_MITIGATOR]: 'RTO Risk Mitigator',
  [AgentName.DAILY_BRIEFING]: 'Daily Briefing',
};

export function agentDisplayName(name: string): string {
  return AGENT_LABEL[name as AgentName] ?? name;
}
```

---

### Task 5 — Frontend API client + trigger hook for briefing

**Files:**
- Modify: `apps/web/src/modules/agent_runs/api/client.ts`
- Create: `apps/web/src/modules/agent_runs/hooks/useTriggerBriefing.ts`

- [ ] **Step 5.1: Extend `agentRunDetailSchema` with optional briefing fields**

In `apps/web/src/modules/agent_runs/api/client.ts`:

```ts
const rowCitationSchema = z.object({
  record_id: z.number(),
  entity_type: z.string(),
  source_system: z.string(),
  source_id: z.string(),
  excerpt: z.record(z.string(), z.unknown()),
});

const proposedActionSchema = z.object({
  action_type: z.string(),
  reasoning: z.string(),
  evidence_record_ids: z.array(z.number()),
});

const agentRunDetailSchema = agentRunSummarySchema.extend({
  decisions: z.array(agentRunDecisionSchema),
  sector: z.string().nullable().optional(),
  narrative: z.string().nullable().optional(),
  proposed_actions: z.array(proposedActionSchema).nullable().optional(),
  citations: z.array(rowCitationSchema).nullable().optional(),
});

export type ProposedAction = z.infer<typeof proposedActionSchema>;
export type RowCitation = z.infer<typeof rowCitationSchema>;
```

Add a new trigger fn:

```ts
export async function triggerBriefing(sector: string) {
  const { data } = await apiPost(`agents/daily_briefing/run`, triggerResponseSchema, {
    searchParams: { sector },
  });
  return data.run;
}
```

(If `apiPost` doesn't support `searchParams`, fall back to building the URL: `agents/daily_briefing/run?sector=${encodeURIComponent(sector)}`. Check the existing `apiPost` signature in `shared/api`.)

- [ ] **Step 5.2: Create `useTriggerBriefing.ts`** modelled on `useTriggerAgent.ts`:

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { triggerBriefing } from '@/modules/agent_runs/api/client';
import { ApiError } from '@/shared/api';
import { useAgentRunMetaStore } from '@/shared/store/agentRunMeta';
import type { Sector } from '@/shared/constants/sectors';

export function useTriggerBriefing() {
  const qc = useQueryClient();
  const setLastTriggeredRunId = useAgentRunMetaStore((s) => s.setLastTriggeredRunId);
  return useMutation({
    mutationFn: (sector: Sector) => triggerBriefing(sector),
    onSuccess: (run) => {
      setLastTriggeredRunId(run.run_log_id);
      toast.success('Briefing ready', {
        description: `${run.actions_proposed} action${run.actions_proposed === 1 ? '' : 's'} proposed.`,
      });
      qc.invalidateQueries({ queryKey: ['agent-runs'] });
    },
    onError: (error: Error) => {
      const traceId = error instanceof ApiError ? `trace: ${error.traceId}` : undefined;
      toast.error('Briefing failed', {
        description: traceId ? `${error.message}\n${traceId}` : error.message,
      });
    },
  });
}
```

---

### Task 6 — Frontend trigger button (sector dropdown) + page header

**Files:**
- Create: `apps/web/src/modules/agent_runs/components/RunBriefingButton.tsx`
- Modify: `apps/web/src/modules/agent_runs/AgentRunsPage.tsx`

- [ ] **Step 6.1: Create `RunBriefingButton.tsx`**

Use the shadcn-style `Select` from `@/shared/ui` if available; otherwise a native `<select>` styled with Tailwind classes that match the existing dropdowns elsewhere in the codebase. Grep for "Select" usage in `apps/web/src/modules/` to match the existing pattern (records source filter, onboarding wizard).

The component:
- Holds local state `sector` (default `Sector.FASHION`).
- Renders a `<Select>` (or `<select>`) with `SECTOR_OPTIONS` mapped to `SECTOR_LABEL`.
- Renders a `<Button>` "Run daily briefing" using `Sparkles` (already imported in EmptyState) or another lucide icon.
- On click: `mutation.mutate(sector)`.

- [ ] **Step 6.2: Update `AgentRunsPage.tsx` header**

Replace `<TriggerAgentButton />` alone with both buttons side-by-side:

```tsx
<div className="flex flex-col gap-2 sm:flex-row sm:items-end">
  <TriggerAgentButton />
  <RunBriefingButton />
</div>
```

Also update the page subtitle so it doesn't only talk about per-order reasoning (since briefings have no per-order reasoning):

```tsx
<p className="mt-1 text-sm text-fg-muted">
  Audit log of every agent run. Click a row to see the full reasoning.
</p>
```

---

### Task 7 — Frontend BriefingDetail component + extract CitedText

**Files:**
- Create: `apps/web/src/modules/chat/components/CitedText.tsx`
- Modify: `apps/web/src/modules/chat/components/MessageBubble.tsx` (refactor to consume CitedText)
- Create: `apps/web/src/modules/agent_runs/components/BriefingDetail.tsx`
- Modify: `apps/web/src/modules/agent_runs/components/RunDetailSheet.tsx`

- [ ] **Step 7.1: Extract `CitedText.tsx`**

Pull the cited-claim regex + UNVERIFIED_SENTINEL handling out of `MessageBubble.tsx` into a standalone component. Same regex (`CITED_CLAIM_RE` and `BARE_CITE_RE`), same `UnverifiedPlaceholder`, same render output. Signature:

```tsx
interface CitedTextProps {
  text: string;
  citations: RowCitation[] | undefined;
}
export function CitedText({ text, citations }: CitedTextProps): ReactElement {
  ...
}
```

Then update `MessageBubble.tsx` to call `<CitedText text={message.text} citations={message.citations} />` instead of inlining the parser. Existing chat behavior must not change — run the chat module's tests after.

- [ ] **Step 7.2: Create `BriefingDetail.tsx`**

Reads from `AgentRunDetail` (`narrative`, `proposed_actions`, `sector`, `citations`). Renders:

```
┌─────────────────────────────────────┐
│ [SECTOR CHIP] · Daily briefing      │
├─────────────────────────────────────┤
│ Narrative (with cited claims as     │
│ dotted-underline tooltips, same as  │
│ chat)                               │
├─────────────────────────────────────┤
│ Proposed actions                    │
│  • Action 1 title                   │
│    Reasoning paragraph (with cites) │
│  • Action 2 title                   │
│    ...                              │
└─────────────────────────────────────┘
```

```tsx
import { Badge } from '@/shared/ui';
import { CitedText } from '@/modules/chat/components/CitedText';
import { SECTOR_LABEL } from '@/shared/constants/sectors';
import type { AgentRunDetail, ProposedAction, RowCitation } from '@/modules/agent_runs/api/client';

interface Props {
  detail: AgentRunDetail;
}

export function BriefingDetail({ detail }: Props) {
  const citations = (detail.citations ?? []) as RowCitation[];
  const sectorLabel = detail.sector ? SECTOR_LABEL[detail.sector as keyof typeof SECTOR_LABEL] ?? detail.sector : null;
  return (
    <>
      <section className="rounded-lg border border-border bg-surface-subtle p-5">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-fg-subtle">
          {sectorLabel && <Badge variant="outline">{sectorLabel}</Badge>}
          <span>weekly briefing</span>
        </div>
        <div className="mt-3 text-sm text-fg leading-relaxed">
          <CitedText text={detail.narrative ?? ''} citations={citations} />
        </div>
      </section>

      {(detail.proposed_actions?.length ?? 0) > 0 && (
        <section>
          <div className="text-xs font-medium uppercase tracking-wider text-fg-subtle mb-3">
            Proposed actions
          </div>
          <div className="flex flex-col gap-3">
            {(detail.proposed_actions ?? []).map((a: ProposedAction, i: number) => (
              <div key={i} className="rounded-lg border border-border bg-surface p-4">
                <div className="text-sm font-medium text-fg">{a.action_type}</div>
                <div className="mt-1.5 text-sm text-fg-muted leading-relaxed">
                  <CitedText text={a.reasoning} citations={citations} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
```

- [ ] **Step 7.3: Branch `RunDetailSheet.tsx` on agent name**

Inside the `{data && (...)}` block, before the existing "Estimated impact" section:

```tsx
{data.agent === 'daily_briefing' ? (
  <BriefingDetail detail={data} />
) : (
  <>
    {/* existing RTO impact + donut + decisions sections */}
  </>
)}
```

The empty `decisions: []` for briefings means the existing per-order sections won't render anyway, but branch explicitly so the "Estimated impact" / "No actions needed" card doesn't appear for briefings (it would show "Result: No actions needed · 0 orders scanned" which is wrong).

- [ ] **Step 7.4: Typecheck + lint**

```bash
cd apps/web
pnpm tsc --noEmit
pnpm lint
```

Expected: clean.

---

### Task 8 — Smoke test, docs, commit

- [ ] **Step 8.1: Local smoke**

Start the local API + web (existing `pnpm dev` flow, exact commands in README). Hit the Agents page in agent-browser:

```bash
agent-browser --auto-connect open http://localhost:5173/agents
agent-browser snapshot -i
# pick the Daily Briefing sector dropdown + button refs, fire it for "Fashion"
agent-browser wait 8000
agent-browser snapshot -i
# verify a new run appears in the table; click into it
```

Verify the detail sheet renders the narrative + proposed actions. If the narrative is empty (TestModel-style trivial output from the LLM under demo data), still proceed — the production demo will have richer data. Note the run id and trace for the changelog.

- [ ] **Step 8.2: Update `context.md`**

Add an entry under "Now" (or whatever the project's section convention is) noting:
- Phase 11 complete: second agent shipped, LLM-driven, sector-aware.
- Architecture decision: kept the deterministic RTO agent for auditability, added an LLM agent for narrative briefings. Both share the chat tools + citation enforcer.
- Lesson learned: any new agent should reuse `chat.tools` so the citation contract stays one path.

- [ ] **Step 8.3: Update `CHANGELOG.md`**

Add a `## 2026-05-17 — phase 11 — daily-briefing agent` entry. List:
- New `daily_briefing` agent (LLM-driven, sector-aware) + `?sector=` query param on the trigger endpoint.
- Sector taxonomy (6 values).
- Frontend: sector dropdown, trigger button, RunDetailSheet branches on agent name.
- Shared `CitedText` component extracted from MessageBubble.

- [ ] **Step 8.4: Update `README.md`**

Find the "What we'd do with another week" section. Remove the "True ROAS Watcher (second agent)" item (since we've now shipped one) — replace it with something else if the section has a recommended length, or just remove. In the "Agents" section (or wherever the existing RTO agent is described), add a paragraph describing the daily-briefing agent and why both agents exist (one deterministic, one LLM-driven; reviewer chooses which pattern matters more).

- [ ] **Step 8.5: Final commit + push**

```bash
git add -A
git commit -m "feat(briefing): ship daily-briefing agent — LLM-driven, sector-aware, second agent"
git push origin main
```

The Render service is `autoDeploy: false`, so the operator manually triggers redeploy from the Render dashboard.

---

## Self-review checklist before declaring done

- All eight tasks have a commit.
- `uv run pytest` passes from `apps/api`.
- `pnpm tsc --noEmit` + `pnpm lint` pass from `apps/web`.
- `context.md` + `CHANGELOG.md` updated in the final commit.
- Local smoke run produced a visible briefing in the UI.
- No `--no-verify` was used; no broad `except Exception:` introduced; no magic strings in branches (sector + agent name both via enums / `as const`).
