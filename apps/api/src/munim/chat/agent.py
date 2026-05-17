"""PydanticAI agent that orchestrates tool calls and produces a
`GroundedAnswer`. The service layer then runs the enforcer over the
answer + the union of citations from every tool call.

We construct the agent on every request (not module-level) so each
request gets its own `RunContext` with the right session + merchant +
trace_id. The model itself is read from `Settings.openai_chat_model`
so swapping to `gpt-4o` or another OpenAI model is one env-var change.
"""

from typing import Any

import httpx
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models import Model

from munim.chat.enforcer import enforce_grounded_answer
from munim.chat.tools import (
    ChatContext,
    compute_metric,
    propose_action,
    query_ad_spend,
    query_orders,
    query_shipments,
)
from munim.chat.types import AnsweredQuestion, GroundedAnswer, RowCitation, ToolResult
from munim.shared.config import get_settings
from munim.shared.constants import ErrorCode, FulfillmentStatus, MetricFormula, PaymentMethod
from munim.shared.errors import MunimError
from munim.shared.logging import get_logger

log = get_logger("munim.chat.agent")


class LLMUnavailableError(MunimError):
    code = ErrorCode.CHAT_LLM_UNAVAILABLE.value
    http_status = 502
    message = "LLM call failed."


_SYSTEM_PROMPT = """You are AI-Munim, an AI employee for an Indian D2C founder.

You help the founder understand their business by pulling real data via the
tools provided and explaining what the data means. You are a thoughtful
assistant, not a database — every answer should explain *why* it's saying
what it's saying, not just *what* the numbers are.

OUTPUT CONTRACT (non-negotiable):
- Output a single `GroundedAnswer` with `text` and `used_citations`.
- Every numerical value in `text` MUST be immediately followed by a cite
  marker of the form `[cite:row_id]` or `[cite:row_id,row_id,...]`, where
  each row_id is taken from the `citations` of a tool result you used.
- Example: "You had 12 orders[cite:1,2,3,4,5,6,7,8,9,10,11,12] worth
  Rs.15,750[cite:1,2,3,4,5,6,7,8,9,10,11,12] this month."
- DERIVED COUNTS NEED CITATIONS TOO. When you say "2 orders at risk", cite
  the 2 rows that ARE the risk set: "2 orders[cite:A,B] at risk". When you
  say "3 of the 5 deliveries were returned", cite the 5 shipments. The cite
  list for a derived count is the union of rows that produced the count.
- If you genuinely do not have a citation for a number, DO NOT state the
  number. Say "a few" or "several" instead, or omit the count.
- `used_citations` lists every row_id you cited in `text`.

STYLE:
- 2-4 sentences is usually the right length. One number plus a period is too
  terse; a long paragraph is too much. Aim for the depth of a smart analyst
  giving the founder a quick read.
- When discussing risks, recommendations, or anomalies, NAME the specific
  factors that drove your conclusion — the pincode, the payment method, the
  customer's prior return history, the time of day, etc. The user can hover
  a citation to see the row; your prose should explain *why* it matters.
- Use Indian rupee formatting: "Rs.2,500" or "₹2,500".
- Don't hedge with "I think" or "it seems". State what the data shows.

TOOLS:
- `query_orders` — Shopify orders. Filter by payment_method, pincode,
  utm_campaign, financial_status.
- `query_shipments` — Shiprocket shipment history. Use `customer_source_id`
  to look up a customer's prior delivered/RTO outcomes BEFORE recommending
  intervention on their pending orders. This is how you go from "this order
  is COD" to "this customer has returned 3 of their last 5 deliveries."
- `query_ad_spend` — Meta Ads campaign-day rows. Use when the user asks
  about marketing spend, campaigns, CTR, or ROAS.
- `compute_metric` — aggregates (sum_total_inr, count_orders) over orders.
- `propose_action` — record a recommendation in the run log. Persisted, no
  external side effects. Use only when the user explicitly asks for an
  action OR when you have a strong recommendation to surface.

WORKFLOW FOR RISK / RECOMMENDATION QUESTIONS:
1. Pull the at-risk orders with `query_orders` (e.g. payment_method='cod').
2. For each candidate, pull the customer's prior shipments with
   `query_shipments(customer_source_id=...)` to see their RTO history.
3. Compose 2-3 sentences that summarise what you found and, when justified,
   recommend an action. Name the factors that mattered."""


def build_agent(model: Model | str | None = None) -> Agent[ChatContext, GroundedAnswer]:
    settings = get_settings()
    model_spec: Model | str
    if model is not None:
        model_spec = model
    else:
        model_spec = f"openai:{settings.openai_chat_model}"

    agent: Agent[ChatContext, GroundedAnswer] = Agent(
        model=model_spec,
        deps_type=ChatContext,
        output_type=GroundedAnswer,
        system_prompt=_SYSTEM_PROMPT,
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

    @agent.tool
    def _compute_metric(
        run_ctx: RunContext[ChatContext],
        formula: MetricFormula,
        payment_method: PaymentMethod | None = None,
        pincode: str | None = None,
    ) -> ToolResult[Any]:
        # Use `Any` (not `Decimal | int`) because PydanticAI's structured
        # output / tool schema generation prefers a single concrete type
        # and our payload varies by formula.
        return compute_metric(
            run_ctx.deps,
            formula=formula,
            payment_method=payment_method,
            pincode=pincode,
        )

    @agent.tool
    def _propose_action(
        run_ctx: RunContext[ChatContext],
        action_type: str,
        target_record_id: int,
        reasoning: str,
        evidence_record_ids: list[int],
    ) -> ToolResult[dict[str, Any]]:
        return propose_action(
            run_ctx.deps,
            action_type=action_type,
            target_record_id=target_record_id,
            reasoning=reasoning,
            evidence_record_ids=evidence_record_ids,
        )

    return agent


async def answer_question(
    question: str,
    ctx: ChatContext,
    *,
    model_override: Model | None = None,
) -> AnsweredQuestion:
    """Run the agent, collect citations from every tool call, run the
    enforcer, return an AnsweredQuestion ready to ship.

    Citation collection: we walk `run_result.all_messages()` and look for
    `ToolReturnPart` instances. In pydantic-ai 1.96.0+, `ToolReturnPart.content`
    holds the raw Python return value of the tool — which for our tools is
    a `ToolResult` instance. We check with `isinstance` before accessing.

    Error handling (per §10 — narrow `except`):
    - `MunimError` subclasses propagate unchanged (our typed domain errors).
    - `ModelHTTPError`, `UnexpectedModelBehavior` (pydantic-ai) and
      `httpx.HTTPError` (network) are wrapped as `LLMUnavailableError` so
      the frontend gets a typed code rather than `system.unexpected`.
    - Anything else propagates — bugs in tools should NOT be classified as
      "LLM unavailable"; let the global handler surface them as
      `system.unexpected` with the stacktrace intact.
    """
    agent = build_agent(model=model_override)

    log.info(
        "chat.agent.run.beginning",
        merchant_id=ctx.merchant_id,
        question_len=len(question),
    )

    try:
        run_result = await agent.run(question, deps=ctx)
    except MunimError:
        raise
    except (ModelHTTPError, UnexpectedModelBehavior, httpx.HTTPError) as exc:
        log.warning(
            "chat.agent.llm_unavailable",
            exc_type=type(exc).__name__,
            merchant_id=ctx.merchant_id,
        )
        raise LLMUnavailableError(
            message="LLM call failed.",
            details={"exc_type": type(exc).__name__, "exc_str": str(exc)[:500]},
        ) from exc

    # Walk message history; every ToolReturnPart whose content is a ToolResult
    # contributes its citations. (pydantic-ai stores the raw Python return value
    # in ToolReturnPart.content — verified empirically for v1.96.0.)
    collected_citations: list[RowCitation] = []
    for message in run_result.all_messages():
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolReturnPart):
                content = part.content
                if isinstance(content, ToolResult):
                    collected_citations.extend(content.citations)

    grounded: GroundedAnswer = run_result.output
    final_text = enforce_grounded_answer(grounded, available_citations=collected_citations)

    # De-dup citations by record_id before returning to the frontend.
    seen: set[int] = set()
    unique_citations: list[RowCitation] = []
    for c in collected_citations:
        if c.record_id not in seen:
            unique_citations.append(c)
            seen.add(c.record_id)

    log.info(
        "chat.agent.run.completed",
        merchant_id=ctx.merchant_id,
        text_len=len(final_text),
        citation_count=len(unique_citations),
    )

    return AnsweredQuestion(text=final_text, citations=unique_citations)
