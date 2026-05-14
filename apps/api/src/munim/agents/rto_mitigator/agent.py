from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, select
from ulid import ULID

from munim.agents.rto_mitigator.scoring import RTODecision, score_signals
from munim.agents.rto_mitigator.signals import (
    SignalResult,
    customer_rto_rate,
    order_value_bucket,
    pincode_risk,
    time_of_order_risk,
)
from munim.models import Record, RunLog
from munim.shared.constants import (
    AgentActionType,
    AgentName,
    EntityType,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)
from munim.shared.logging import get_logger

log = get_logger("munim.agents.rto_mitigator")


@dataclass
class AgentRunSummary:
    run_id: str
    run_log_id: int
    orders_scanned: int
    actions_proposed: int
    started_at: datetime
    finished_at: datetime


class RTOMitigatorAgent:
    name = AgentName.RTO_MITIGATOR

    def run(self, session: Session, merchant_id: str) -> AgentRunSummary:
        started_at = datetime.now(UTC)
        run_id = f"ar_{ULID()}"

        orders = self._scan_cod_orders(session, merchant_id)
        decisions = [self._score_order(session, merchant_id, o) for o in orders]
        actions_proposed = sum(
            1 for d in decisions if d["action"] != AgentActionType.NO_ACTION.value
        )

        finished_at = datetime.now(UTC)

        run = RunLog(
            merchant_id=merchant_id,
            kind=RunLogKind.AGENT.value,
            started_at=started_at,
            finished_at=finished_at,
            detail_json={
                "run_id": run_id,
                "agent": self.name.value,
                "orders_scanned": len(orders),
                "actions_proposed": actions_proposed,
                "decisions": decisions,
            },
        )
        session.add(run)
        session.flush()

        log.info(
            "agent.run.completed",
            agent=self.name.value,
            run_id=run_id,
            merchant_id=merchant_id,
            orders_scanned=len(orders),
            actions_proposed=actions_proposed,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        )

        assert run.id is not None
        return AgentRunSummary(
            run_id=run_id,
            run_log_id=run.id,
            orders_scanned=len(orders),
            actions_proposed=actions_proposed,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _scan_cod_orders(self, session: Session, merchant_id: str) -> list[Record]:
        stmt = (
            select(Record)
            .where(Record.merchant_id == merchant_id)
            .where(Record.source_system == SourceSystem.SHOPIFY.value)
            .where(Record.entity_type == EntityType.ORDER.value)
            .order_by(col(Record.fetched_at).desc())
        )
        all_orders = session.exec(stmt).all()
        return [
            r for r in all_orders if r.normalized.get("payment_method") == PaymentMethod.COD.value
        ]

    def _score_order(self, session: Session, merchant_id: str, order: Record) -> dict[str, Any]:
        n = order.normalized
        total_inr = Decimal(n["total_inr"])

        signals: dict[str, SignalResult] = {
            "value": order_value_bucket(total_inr),
            "pincode": pincode_risk(n.get("pincode")),
            "time": time_of_order_risk(n["placed_at"]),
            "customer": customer_rto_rate(session, merchant_id, n.get("customer_source_id", "")),
        }
        decision: RTODecision = score_signals(signals, total_inr=total_inr)

        assert order.id is not None
        return {
            "record_id": order.id,
            "source_id": order.source_id,
            "score": decision.score,
            "action": decision.action.value,
            "estimated_inr_saved": str(decision.estimated_inr_saved),
            "signal_scores": decision.signal_scores,
            "signal_diagnostics": decision.signal_diagnostics,
            "weights": decision.weights.model_dump(),
            "reasoning": decision.reasoning,
        }
