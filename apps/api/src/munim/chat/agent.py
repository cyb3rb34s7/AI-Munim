"""PydanticAI agent that orchestrates tool calls and produces a
`GroundedAnswer`. The service layer then runs the enforcer over the
answer + the union of citations from every tool call.

We construct the agent on every request (not module-level) so each
request gets its own `RunContext` with the right session + merchant.
The model itself is read from `Settings.openai_chat_model` so swapping
to `gpt-4o` or another OpenAI model is one env-var change.
"""

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models import Model

from munim.chat.enforcer import enforce_grounded_answer
from munim.chat.tools import (
    ChatContext,
    compute_metric,
    propose_action,
    query_orders,
)
from munim.chat.types import AnsweredQuestion, GroundedAnswer, RowCitation, ToolResult
from munim.shared.config import get_settings
from munim.shared.constants import ErrorCode, PaymentMethod
from munim.shared.errors import MunimError

_SYSTEM_PROMPT = """You are AI-Munim, an AI employee for a D2C founder.

You answer questions about the founder's business by calling the tools
provided. Every tool returns rows of source data alongside the answer.

OUTPUT CONTRACT (non-negotiable):
- Output a single `GroundedAnswer` with `text` and `used_citations`.
- Every numerical value in `text` MUST be immediately followed by a cite
  marker of the form `[cite:row_id]` or `[cite:row_id,row_id,...]`, where
  each row_id is taken from the `citations` of a tool result you used.
- Example: "You had 12 orders[cite:1,2,3,4,5,6,7,8,9,10,11,12] worth
  Rs.15750[cite:1,2,3,4,5,6,7,8,9,10,11,12] this month."
- If you do not have a citation for a number, DO NOT state the number.
  Say "[unknown]" instead.
- `used_citations` lists the row_ids you actually referenced in `text`.

Tools available:
- `query_orders` — filter orders by payment_method, pincode, utm_campaign,
  financial_status. Returns the matching rows.
- `compute_metric` — compute `sum_total_inr` or `count_orders` over filtered
  orders. Returns the scalar plus the rows that contributed.
- `propose_action` — record a proposed action (e.g., convert a COD order to
  prepaid). Persisted to the run log; does NOT dispatch any message. Use
  only when the user explicitly asks for an action.

Style: terse, founder-friendly, no hedging. If you don't have data, say so."""


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
    def _compute_metric(
        run_ctx: RunContext[ChatContext],
        formula: str,
        payment_method: PaymentMethod | None = None,
        pincode: str | None = None,
    ) -> ToolResult[Any]:
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
    `ToolReturnPart` instances. In pydantic-ai v0.4+, `ToolReturnPart.content`
    holds the raw Python return value of the tool — which for our tools is
    a `ToolResult` instance. We check with `isinstance` before accessing.
    """
    agent = build_agent(model=model_override)

    try:
        run_result = await agent.run(question, deps=ctx)
    except MunimError:
        # Re-raise typed domain errors (e.g., UnknownMetricFormulaError) unchanged
        # so the global error handler can classify them correctly.
        raise
    except Exception as exc:
        raise LLMUnavailableError(
            message=f"LLM call failed: {exc}",
            details={"exc_type": type(exc).__name__},
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

    return AnsweredQuestion(text=final_text, citations=unique_citations)


class LLMUnavailableError(MunimError):
    code = ErrorCode.CHAT_LLM_UNAVAILABLE.value
    http_status = 502
    message = "LLM call failed."
