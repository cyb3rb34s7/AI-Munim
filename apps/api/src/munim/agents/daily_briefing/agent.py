"""LLM-driven daily-briefing agent.

Reuses the chat tools (`query_orders`, `query_shipments`, `query_ad_spend`)
via PydanticAI tool registration. Sector is spliced into the system prompt
when the agent is built — one Agent instance per (request, sector) pair.

The agent's structured output is `BriefingOutput`. The service then runs
the citation enforcer against the narrative (and each action's reasoning)
using the union of citations returned by the tools, exactly like the chat
flow.
"""

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from munim.agents.daily_briefing.constants import SECTOR_HINT, SECTOR_LABEL, Sector
from munim.agents.daily_briefing.schemas import BriefingOutput
from munim.chat.tools import ChatContext, query_ad_spend, query_orders, query_shipments
from munim.chat.types import ToolResult
from munim.shared.config import get_settings
from munim.shared.constants import FulfillmentStatus, PaymentMethod

_SYSTEM_PROMPT_TEMPLATE = """You are the daily-briefing AI employee for an Indian
D2C brand on Shopify, Meta Ads, and Shiprocket. Sector: {sector_label}.

Your job: compose a 7-day weekly briefing the owner reads in under a minute.
Output a BriefingOutput with:
- narrative: 4-6 sentences. Cover what happened, what's notable, what's
  concerning. Plain English, no jargon.
- proposed_actions: 0-3 concrete actions the owner should take. Each has a
  short reasoning string and evidence_record_ids.
- used_citations: union of every row_id cited in narrative or proposed_actions.

SECTOR FOCUS: {sector_hint}

CITATION CONTRACT (non-negotiable):
- Every numerical value in `narrative` AND in each action's `reasoning` MUST
  be immediately followed by `[cite:row_id]` or `[cite:row_id,row_id,...]`,
  where each row_id is taken from the citations of a tool result you used.
- DERIVED COUNTS NEED CITATIONS TOO. "3 orders[cite:1,2,3]" — cite all 3
  rows that produced the count.
- If you genuinely don't have a citation for a number, DO NOT state it. Say
  "a few" or "several" instead, or omit the count.

TOOL CALLING DISCIPLINE (non-negotiable):
- ONE pass, then write. Call each of query_orders, query_shipments, and
  query_ad_spend AT MOST TWICE total across the entire run (e.g., one
  unfiltered scan + at most one filtered follow-up per tool).
- DO NOT re-query the same filters hoping for new data — the data is static
  for this run. If a query returned 0 rows, it will return 0 rows again.
- After ~6 tool calls total, STOP querying and compose the BriefingOutput
  with what you have. Citing fewer rows is fine; an infinite loop is not.

WORKFLOW:
1. ONE unfiltered query_orders, ONE unfiltered query_shipments, ONE
   unfiltered query_ad_spend. That's it for scanning.
2. Optionally, ONE filtered follow-up per tool if you spotted something
   worth drilling into (e.g., query_shipments with a specific customer id).
3. Compose narrative + 0-3 specific actions FROM the rows you already have.

STYLE:
- Open with the period: "This week..." or "Over the last 7 days...".
- Name specific factors when proposing actions (the customer's prior return
  rate, the pincode, the campaign name).
- Use Indian rupee formatting: "Rs.2,500" or "₹2,500".
- Don't hedge. State what the data shows.
"""


def build_agent(
    sector: Sector,
    model: Model | str | None = None,
) -> Agent[ChatContext, BriefingOutput]:
    settings = get_settings()
    model_spec: Model | str = model if model is not None else f"openai:{settings.openai_chat_model}"

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        sector_label=SECTOR_LABEL[sector],
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
