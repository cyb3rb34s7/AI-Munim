"""Tool functions backed by real `record` rows. Tests use the existing
`session` fixture from `apps/api/conftest.py` and seed Shopify-shaped
data directly into the DB so we don't need a live OpenAI call for these.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session

from munim.chat.tools import (
    ChatContext,
    compute_metric,
    propose_action,
    query_orders,
)
from munim.models import Record, RunLog
from munim.shared.constants import (
    EntityType,
    MetricFormula,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)

DEFAULT_MERCHANT_ID = "m_default"


def _make_record(
    session: Session,
    *,
    source_id: str,
    total_inr: str,
    payment_method: str,
    pincode: str = "560001",
    utm_campaign: str | None = "meta_summer",
    financial_status: str = "pending",
    placed_at: str = "2026-05-10T03:45:32Z",
) -> Record:
    normalized: dict[str, Any] = {
        "placed_at": placed_at,
        "total_inr": total_inr,
        "currency": "INR",
        "payment_method": payment_method,
        "financial_status": financial_status,
        "fulfillment_status": None,
        "pincode": pincode,
        "customer_source_id": "9802477207847",
        "utm_campaign": utm_campaign,
        "line_items_count": 1,
    }
    row = Record(
        merchant_id=DEFAULT_MERCHANT_ID,
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"hash_{source_id}",
        raw={"id": source_id, "current_total_price": total_inr},
        normalized=normalized,
    )
    session.add(row)
    session.flush()
    return row


def _ctx(session: Session) -> ChatContext:
    return ChatContext(merchant_id=DEFAULT_MERCHANT_ID, session=session)


def test_query_orders_returns_rows_with_citations(session: Session) -> None:
    a = _make_record(session, source_id="A", total_inr="1249.00", payment_method="cod")
    b = _make_record(session, source_id="B", total_inr="2199.00", payment_method="prepaid")
    session.commit()

    result = query_orders(_ctx(session))
    assert len(result.data) == 2
    cited_ids = {c.record_id for c in result.citations}
    assert cited_ids == {a.id, b.id}


def test_query_orders_filters_by_payment_method(session: Session) -> None:
    cod = _make_record(session, source_id="A", total_inr="100", payment_method="cod")
    _make_record(session, source_id="B", total_inr="200", payment_method="prepaid")
    session.commit()

    result = query_orders(_ctx(session), payment_method=PaymentMethod.COD)
    assert len(result.data) == 1
    assert result.citations[0].record_id == cod.id


def test_query_orders_filters_by_pincode(session: Session) -> None:
    blr = _make_record(
        session, source_id="A", total_inr="100", payment_method="cod", pincode="560001"
    )
    _make_record(
        session, source_id="B", total_inr="200", payment_method="prepaid", pincode="110001"
    )
    session.commit()

    result = query_orders(_ctx(session), pincode="560001")
    assert len(result.data) == 1
    assert result.citations[0].record_id == blr.id


def test_query_orders_filters_by_utm_campaign(session: Session) -> None:
    a = _make_record(
        session, source_id="A", total_inr="100", payment_method="cod", utm_campaign="meta_summer"
    )
    _make_record(
        session, source_id="B", total_inr="200", payment_method="cod", utm_campaign="google_search"
    )
    session.commit()

    result = query_orders(_ctx(session), utm_campaign="meta_summer")
    assert len(result.data) == 1
    assert result.citations[0].record_id == a.id


def test_compute_metric_sum_total_inr(session: Session) -> None:
    a = _make_record(session, source_id="A", total_inr="1249.50", payment_method="cod")
    b = _make_record(session, source_id="B", total_inr="2199.50", payment_method="prepaid")
    session.commit()

    result = compute_metric(_ctx(session), formula=MetricFormula.SUM_TOTAL_INR)
    assert result.data == Decimal("3449.00")
    cited = {c.record_id for c in result.citations}
    assert cited == {a.id, b.id}


def test_compute_metric_count_orders(session: Session) -> None:
    for i in range(5):
        _make_record(session, source_id=f"X{i}", total_inr="100", payment_method="cod")
    session.commit()

    result = compute_metric(_ctx(session), formula=MetricFormula.COUNT_ORDERS)
    assert result.data == 5
    assert len(result.citations) == 5


def test_compute_metric_unhandled_formula_raises(session: Session) -> None:
    # Defensive: if `MetricFormula` ever gains a new variant and we forget
    # to handle it in `compute_metric`, the `else` branch raises rather
    # than returning silently-wrong data. Force the defensive path with a
    # cast (Pydantic coercion at the PydanticAI tool boundary catches
    # malformed strings before reaching here in the real flow).
    from typing import cast

    from munim.chat.tools import UnknownMetricFormulaError

    with pytest.raises(UnknownMetricFormulaError):
        compute_metric(_ctx(session), formula=cast(MetricFormula, "madeup_metric"))


def test_compute_metric_with_empty_result_set_returns_zero(session: Session) -> None:
    # Reviewer-flagged edge case: when no rows match the filter, sum is
    # Decimal("0") with citations=[]. A model that then cites [cite:0] in
    # the answer would get rejected by the enforcer (0 not in available_ids).
    # This test pins the tool-level invariant — the enforcer test covers
    # the cross-check.
    result = compute_metric(_ctx(session), formula=MetricFormula.SUM_TOTAL_INR)
    assert result.data == Decimal("0")
    assert result.citations == []


def test_propose_action_writes_run_log_no_side_effect(session: Session) -> None:
    # propose_action is the only "write" tool in v0; per the brief and
    # docs/architecture.md §8 the agent NEVER dispatches messages or
    # modifies external state. It only persists the proposed action to
    # `run_log` for human review.
    a = _make_record(session, source_id="A", total_inr="1249", payment_method="cod")
    session.commit()
    assert a.id is not None  # flushed by _make_record

    ctx = ChatContext(merchant_id=DEFAULT_MERCHANT_ID, session=session, trace_id="tr_test_001")
    result = propose_action(
        ctx,
        action_type="convert_to_prepaid",
        target_record_id=a.id,
        reasoning="High RTO risk on this pincode.",
        evidence_record_ids=[a.id],
    )
    session.commit()

    # The run_log row exists and references the evidence rows.
    from sqlmodel import select

    runs = session.exec(select(RunLog)).all()
    assert len(runs) == 1
    # No magic strings per §7 — compare against the enum value.
    assert runs[0].kind == RunLogKind.CHAT.value
    assert runs[0].detail_json["action_type"] == "convert_to_prepaid"
    # trace_id was stamped into detail_json per §5.2.
    assert runs[0].detail_json["trace_id"] == "tr_test_001"
    # The tool returns the run_log row id as data + the evidence as citations.
    assert result.data["run_log_id"] == runs[0].id
    assert {c.record_id for c in result.citations} == {a.id}


def test_row_to_citation_raises_when_id_is_none(session: Session) -> None:
    # Reviewer-flagged silent fallback: previously `_row_to_citation` did
    # `record_id=row.id if row.id is not None else 0`. A `record_id=0`
    # citation could match a real row id and "verify" a hallucination.
    # The right behavior is to raise; flushing before citing is the
    # caller's job.
    from munim.chat.tools import _row_to_citation

    unflushed = Record(
        merchant_id=DEFAULT_MERCHANT_ID,
        source_system=SourceSystem.SHOPIFY.value,
        source_id="not_flushed",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="h",
        raw={},
        normalized={},
    )
    # Don't add to session; id is None.
    assert unflushed.id is None
    with pytest.raises(ValueError, match="flush"):
        _row_to_citation(unflushed)
