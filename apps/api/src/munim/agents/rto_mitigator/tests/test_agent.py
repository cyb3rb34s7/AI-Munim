from datetime import UTC, datetime
from decimal import Decimal

import respx
from sqlmodel import Session, select

from munim.agents.rto_mitigator.agent import RTOMitigatorAgent
from munim.models import Record, RunLog
from munim.shared.constants import (
    AgentActionType,
    AgentName,
    EntityType,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)


def _seed_order(
    session: Session,
    *,
    source_id: str,
    payment_method: PaymentMethod,
    total_inr: str = "1500",
    pincode: str = "110001",
    customer_source_id: str = "cust_a",
    placed_at: str = "2026-05-10T23:45:00+05:30",
) -> Record:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized={
            "placed_at": placed_at,
            "total_inr": total_inr,
            "currency": "INR",
            "payment_method": payment_method.value,
            "financial_status": "pending",
            "pincode": pincode,
            "customer_source_id": customer_source_id,
        },
    )
    session.add(row)
    session.flush()
    return row


def test_agent_only_scores_cod_orders(session: Session) -> None:
    cod = _seed_order(session, source_id="cod_1", payment_method=PaymentMethod.COD)
    _seed_order(session, source_id="prepaid_1", payment_method=PaymentMethod.PREPAID)
    session.commit()

    agent = RTOMitigatorAgent()
    summary = agent.run(session, merchant_id="m_default")
    session.commit()

    assert summary.orders_scanned == 1
    run = session.exec(select(RunLog)).one()
    decisions = run.detail_json["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["record_id"] == cod.id


def test_agent_writes_one_run_log_with_all_decisions(session: Session) -> None:
    for i in range(3):
        _seed_order(session, source_id=f"cod_{i}", payment_method=PaymentMethod.COD)
    session.commit()

    agent = RTOMitigatorAgent()
    summary = agent.run(session, merchant_id="m_default")
    session.commit()

    runs = session.exec(select(RunLog).where(RunLog.kind == RunLogKind.AGENT.value)).all()
    assert len(runs) == 1
    assert summary.orders_scanned == 3
    assert len(runs[0].detail_json["decisions"]) == 3
    assert runs[0].detail_json["agent"] == AgentName.RTO_MITIGATOR.value


def test_agent_decision_includes_signal_scores_and_weights(session: Session) -> None:
    _seed_order(session, source_id="cod_x", payment_method=PaymentMethod.COD)
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    d = run.detail_json["decisions"][0]
    assert "signal_scores" in d
    assert "weights" in d
    assert "value" in d["signal_scores"]
    assert "pincode" in d["signal_scores"]


def test_agent_proposes_convert_for_high_risk_cod_order(session: Session) -> None:
    for i in range(3):
        row = _seed_order(
            session,
            source_id=f"hist_rto_{i}",
            payment_method=PaymentMethod.COD,
            total_inr="1000",
            customer_source_id="repeat_rto_cust",
        )
        row.normalized = {**row.normalized, "fulfillment_status": "rto"}
        session.add(row)
    _seed_order(
        session,
        source_id="high_risk",
        payment_method=PaymentMethod.COD,
        total_inr="6000",
        pincode="110001",
        customer_source_id="repeat_rto_cust",
        placed_at="2026-05-10T23:30:00+05:30",
    )
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    high_risk_decision = next(
        d for d in run.detail_json["decisions"] if d["source_id"] == "high_risk"
    )
    assert high_risk_decision["action"] == AgentActionType.CONVERT_TO_PREPAID.value
    assert Decimal(high_risk_decision["estimated_inr_saved"]) > Decimal("0")


@respx.mock
def test_agent_makes_zero_outbound_http_calls(session: Session) -> None:
    _seed_order(session, source_id="cod_1", payment_method=PaymentMethod.COD)
    _seed_order(
        session,
        source_id="cod_2",
        payment_method=PaymentMethod.COD,
        total_inr="6000",
        pincode="110001",
    )
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    assert len(respx.calls) == 0


def test_agent_run_log_has_run_id_and_timing(session: Session) -> None:
    _seed_order(session, source_id="cod_a", payment_method=PaymentMethod.COD)
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    assert run.detail_json["run_id"].startswith("ar_")
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at


def test_agent_with_zero_cod_orders_still_writes_empty_run_log(session: Session) -> None:
    _seed_order(session, source_id="prepaid_only", payment_method=PaymentMethod.PREPAID)
    session.commit()

    summary = RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    assert summary.orders_scanned == 0
    assert summary.actions_proposed == 0
    runs = session.exec(select(RunLog)).all()
    assert len(runs) == 1
    assert runs[0].detail_json["decisions"] == []
