"""Typed tools the chat agent calls. Each tool reads from the `record` table
filtered by `merchant_id` and returns a `ToolResult` carrying both the data
and the `RowCitation`s of the rows that produced it.

`propose_action` is the only "write" tool — it persists the proposed action
to `run_log` for a human to review. No external side effects. Matches the
brief's "AI employee proposes, doesn't dispatch" constraint.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, select

from munim.chat.types import RowCitation, ToolResult
from munim.models import Record, RunLog
from munim.shared.constants import (
    EntityType,
    ErrorCode,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)
from munim.shared.errors import MunimError


class UnknownMetricFormulaError(MunimError):
    code = ErrorCode.CHAT_TOOL_FAILED.value
    http_status = 400
    message = "Unknown metric formula."


@dataclass
class ChatContext:
    """Bag of dependencies the tools share. Passed into each tool by the
    agent's `RunContext`.
    """

    merchant_id: str
    session: Session


def _row_to_citation(row: Record, fields: list[str] | None = None) -> RowCitation:
    if fields is None:
        excerpt = dict(row.normalized)
    else:
        excerpt = {k: row.normalized.get(k) for k in fields}
    return RowCitation(
        record_id=row.id if row.id is not None else 0,
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
    return ToolResult(data=data, citations=citations)


def compute_metric(
    ctx: ChatContext,
    *,
    formula: str,
    payment_method: PaymentMethod | None = None,
    pincode: str | None = None,
) -> ToolResult[Decimal | int]:
    """Aggregate over the filtered order set. `formula` is one of:
      - `sum_total_inr` — sum of `total_inr` over orders matching the filter.
      - `count_orders` — count of orders matching the filter.

    Citations include every row that contributed to the aggregate.
    """
    filtered = query_orders(
        ctx,
        payment_method=payment_method,
        pincode=pincode,
    )

    if formula == "sum_total_inr":
        total = sum((Decimal(d["total_inr"]) for d in filtered.data), start=Decimal("0"))
        return ToolResult(data=total, citations=filtered.citations)
    if formula == "count_orders":
        return ToolResult(data=len(filtered.data), citations=filtered.citations)

    raise UnknownMetricFormulaError(
        message=f"Unknown metric formula: {formula!r}. Known: sum_total_inr, count_orders.",
        details={"formula": formula},
    )


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
        },
    )
    ctx.session.add(run)
    ctx.session.flush()

    evidence_rows = ctx.session.exec(
        select(Record).where(col(Record.id).in_(evidence_record_ids))
    ).all()
    citations = [_row_to_citation(r) for r in evidence_rows]

    return ToolResult(
        data={
            "run_log_id": run.id,
            "action_type": action_type,
            "target_record_id": target_record_id,
        },
        citations=citations,
    )
