"""Typed tools the chat agent calls. Each tool reads from the `record` table
filtered by `merchant_id` and returns a `ToolResult` carrying both the data
and the `RowCitation`s of the rows that produced it.

`propose_action` is the only "write" tool — it persists the proposed action
to `run_log` (with `trace_id` for auditability per docs/conventions.md §5.2)
for a human to review. No external side effects. Matches the brief's
"AI employee proposes, doesn't dispatch" constraint.

Structured logging via `get_logger` per §5.3: every tool call emits one
`chat.tool.invoked` event with the bound trace_id (set by the request
middleware) so a debugging operator can grep one trace across HTTP →
tool calls → DB writes.
"""

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, select

from munim.chat.types import RowCitation, ToolResult
from munim.models import Record, RunLog
from munim.shared.constants import (
    EntityType,
    ErrorCode,
    FulfillmentStatus,
    MetricFormula,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)
from munim.shared.errors import MunimError
from munim.shared.logging import get_logger

log = get_logger("munim.chat.tools")


class UnknownMetricFormulaError(MunimError):
    code = ErrorCode.CHAT_TOOL_FAILED.value
    http_status = 400
    message = "Unknown metric formula."


@dataclass
class ChatContext:
    """Bag of dependencies the tools share. Passed into each tool by the
    agent's `RunContext`. `trace_id` is set from `request.state.trace_id`
    so tool writes can record it (§5.2).

    `session_lock` serialises DB access across tool calls. PydanticAI
    executes sync tools in worker threads via `anyio.to_thread.run_sync`;
    when the LLM emits multiple tool calls in a single response (parallel
    tool-use), all worker threads share this `Session`, and SQLAlchemy
    raises `InvalidRequestError: concurrent operations are not permitted`.
    Every tool function MUST hold `session_lock` for the duration of its
    DB interaction. Production traceback that surfaced this:
    https://github.com/.../issues/N (Phase 11 daily-briefing).
    """

    merchant_id: str
    session: Session
    trace_id: str | None = None
    session_lock: threading.Lock = field(default_factory=threading.Lock)


def _row_to_citation(row: Record, fields: list[str] | None = None) -> RowCitation:
    # Per §10 (no silent fallbacks): a `record.id` of None means the row
    # wasn't flushed, which is a programming bug — fail loudly instead of
    # citing "row 0" which would (a) be incorrect and (b) potentially
    # match a real row id and falsely-verify a hallucination.
    if row.id is None:
        raise ValueError(
            "Cannot cite a record before session.flush() — record.id is None. "
            "This is a bug in the caller; flush before building citations."
        )
    if fields is None:
        excerpt = dict(row.normalized)
    else:
        excerpt = {k: row.normalized.get(k) for k in fields}
    return RowCitation(
        record_id=row.id,
        entity_type=row.entity_type,
        source_system=row.source_system,
        source_id=row.source_id,
        excerpt=excerpt,
    )


def query_orders(
    ctx: ChatContext,
    *,
    payment_method: PaymentMethod | None = None,
    pincode: str | None = None,
    utm_campaign: str | None = None,
    financial_status: str | None = None,
) -> ToolResult[list[dict[str, Any]]]:
    """Filter Shopify orders by common attributes. Returns a list of order
    dicts (`normalized` JSON) plus citations pointing to each row.
    """
    stmt = (
        select(Record)
        .where(Record.merchant_id == ctx.merchant_id)
        .where(Record.source_system == SourceSystem.SHOPIFY.value)
        .where(Record.entity_type == EntityType.ORDER.value)
        .order_by(col(Record.fetched_at).desc())
    )
    with ctx.session_lock:
        rows = ctx.session.exec(stmt).all()

    def matches(row: Record) -> bool:
        n = row.normalized
        if payment_method is not None and n.get("payment_method") != payment_method.value:
            return False
        if pincode is not None and n.get("pincode") != pincode:
            return False
        if utm_campaign is not None and n.get("utm_campaign") != utm_campaign:
            return False
        if financial_status is not None and n.get("financial_status") != financial_status:
            return False
        return True

    matched = [r for r in rows if matches(r)]
    data = [dict(r.normalized) for r in matched]
    citations = [
        _row_to_citation(r, fields=["placed_at", "total_inr", "payment_method", "pincode"])
        for r in matched
    ]
    log.info(
        "chat.tool.invoked",
        tool="query_orders",
        merchant_id=ctx.merchant_id,
        row_count=len(matched),
        filters={
            "payment_method": payment_method.value if payment_method else None,
            "pincode": pincode,
            "utm_campaign": utm_campaign,
            "financial_status": financial_status,
        },
    )
    return ToolResult(data=data, citations=citations)


def query_shipments(
    ctx: ChatContext,
    *,
    customer_source_id: str | None = None,
    fulfillment_status: FulfillmentStatus | None = None,
    pincode: str | None = None,
) -> ToolResult[list[dict[str, Any]]]:
    """Filter Shiprocket shipments. The most useful filter is
    `customer_source_id` — look up a customer's prior shipment outcomes
    (delivered vs RTO) before recommending action on their pending orders.
    """
    stmt = (
        select(Record)
        .where(Record.merchant_id == ctx.merchant_id)
        .where(Record.source_system == SourceSystem.SHIPROCKET.value)
        .where(Record.entity_type == EntityType.SHIPMENT.value)
        .order_by(col(Record.fetched_at).desc())
    )
    with ctx.session_lock:
        rows = ctx.session.exec(stmt).all()

    def matches(row: Record) -> bool:
        n = row.normalized
        if customer_source_id is not None and n.get("customer_source_id") != customer_source_id:
            return False
        if (
            fulfillment_status is not None
            and n.get("fulfillment_status") != fulfillment_status.value
        ):
            return False
        if pincode is not None and n.get("pincode") != pincode:
            return False
        return True

    matched = [r for r in rows if matches(r)]
    data = [dict(r.normalized) for r in matched]
    citations = [
        _row_to_citation(
            r,
            fields=[
                "fulfillment_status",
                "courier_name",
                "total_inr",
                "placed_at",
                "pincode",
                "customer_source_id",
            ],
        )
        for r in matched
    ]
    log.info(
        "chat.tool.invoked",
        tool="query_shipments",
        merchant_id=ctx.merchant_id,
        row_count=len(matched),
        filters={
            "customer_source_id": customer_source_id,
            "fulfillment_status": fulfillment_status.value if fulfillment_status else None,
            "pincode": pincode,
        },
    )
    return ToolResult(data=data, citations=citations)


def query_ad_spend(
    ctx: ChatContext,
    *,
    campaign_name: str | None = None,
) -> ToolResult[list[dict[str, Any]]]:
    """Filter Meta Ads campaign-day rows. Use when the user asks about
    marketing spend, campaign performance, ROAS, or CTR.
    """
    stmt = (
        select(Record)
        .where(Record.merchant_id == ctx.merchant_id)
        .where(Record.source_system == SourceSystem.META_ADS.value)
        .where(Record.entity_type == EntityType.AD_SPEND.value)
        .order_by(col(Record.fetched_at).desc())
    )
    with ctx.session_lock:
        rows = ctx.session.exec(stmt).all()

    def matches(row: Record) -> bool:
        n = row.normalized
        if campaign_name is not None and n.get("campaign_name") != campaign_name:
            return False
        return True

    matched = [r for r in rows if matches(r)]
    data = [dict(r.normalized) for r in matched]
    citations = [
        _row_to_citation(
            r,
            fields=[
                "campaign_name",
                "date",
                "spend_inr",
                "impressions",
                "clicks",
                "ctr",
                "purchases_attributed",
            ],
        )
        for r in matched
    ]
    log.info(
        "chat.tool.invoked",
        tool="query_ad_spend",
        merchant_id=ctx.merchant_id,
        row_count=len(matched),
        filters={"campaign_name": campaign_name},
    )
    return ToolResult(data=data, citations=citations)


def compute_metric(
    ctx: ChatContext,
    *,
    formula: MetricFormula,
    payment_method: PaymentMethod | None = None,
    pincode: str | None = None,
) -> ToolResult[Decimal | int]:
    """Aggregate over the filtered order set. `formula` is one of:
      - `MetricFormula.SUM_TOTAL_INR` — sum of `total_inr` over filter.
      - `MetricFormula.COUNT_ORDERS` — count of matched orders.

    Citations include every row that contributed to the aggregate.
    """
    filtered = query_orders(ctx, payment_method=payment_method, pincode=pincode)

    result: Decimal | int
    if formula is MetricFormula.SUM_TOTAL_INR:
        result = sum((Decimal(d["total_inr"]) for d in filtered.data), start=Decimal("0"))
    elif formula is MetricFormula.COUNT_ORDERS:
        result = len(filtered.data)
    else:
        # Unreachable when typed correctly; defensive in case the LLM
        # passes an unknown string and PydanticAI didn't coerce to enum.
        raise UnknownMetricFormulaError(
            message=f"Unknown metric formula: {formula!r}.",
            details={"formula": str(formula)},
        )

    log.info(
        "chat.tool.invoked",
        tool="compute_metric",
        merchant_id=ctx.merchant_id,
        formula=formula.value,
        rows_aggregated=len(filtered.citations),
        result_kind=type(result).__name__,
    )
    return ToolResult(data=result, citations=filtered.citations)


def propose_action(
    ctx: ChatContext,
    *,
    action_type: str,
    target_record_id: int,
    reasoning: str,
    evidence_record_ids: list[int],
) -> ToolResult[dict[str, Any]]:
    """Persist a proposed action to `run_log`. NO external side effects.
    The human sees the proposal in the agent runs view (Phase 8) and
    decides whether to act.

    `trace_id` is stamped into `detail_json` per §5.2 — every run_log
    row written by the system carries the originating request's trace.
    """
    now = datetime.now(UTC)
    run = RunLog(
        merchant_id=ctx.merchant_id,
        kind=RunLogKind.CHAT.value,
        started_at=now,
        finished_at=now,
        detail_json={
            "action_type": action_type,
            "target_record_id": target_record_id,
            "reasoning": reasoning,
            "evidence_record_ids": evidence_record_ids,
            "trace_id": ctx.trace_id,
        },
    )
    with ctx.session_lock:
        ctx.session.add(run)
        ctx.session.flush()
        evidence_rows = ctx.session.exec(
            select(Record).where(col(Record.id).in_(evidence_record_ids))
        ).all()
    citations = [_row_to_citation(r) for r in evidence_rows]

    log.info(
        "chat.tool.invoked",
        tool="propose_action",
        merchant_id=ctx.merchant_id,
        action_type=action_type,
        target_record_id=target_record_id,
        evidence_count=len(evidence_record_ids),
        run_log_id=run.id,
    )

    return ToolResult(
        data={
            "run_log_id": run.id,
            "action_type": action_type,
            "target_record_id": target_record_id,
        },
        citations=citations,
    )
