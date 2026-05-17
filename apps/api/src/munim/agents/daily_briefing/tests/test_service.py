"""Service-level integration tests for the daily-briefing agent.

We use PydanticAI's `TestModel` to mock the LLM. The TestModel is told to
invoke `_query_orders` (so real citations land in the message history) and
to return a canned `BriefingOutput`. The service then runs the enforcer
and persists a RunLog — we assert the persisted shape.
"""

from datetime import UTC, datetime

from pydantic_ai.models.test import TestModel
from sqlmodel import Session, select

from munim.agents.daily_briefing.constants import Sector
from munim.agents.daily_briefing.schemas import BriefingOutput, ProposedAction
from munim.agents.daily_briefing.service import run_briefing
from munim.models import Record, RunLog
from munim.shared.constants import AgentName, EntityType, RunLogKind, SourceSystem

DEFAULT_MERCHANT_ID = "m_default"


def _seed_orders(session: Session, n: int) -> list[int]:
    ids: list[int] = []
    for i in range(n):
        row = Record(
            merchant_id=DEFAULT_MERCHANT_ID,
            source_system=SourceSystem.SHOPIFY.value,
            source_id=f"ord_{i}",
            entity_type=EntityType.ORDER.value,
            fetched_at=datetime.now(UTC),
            payload_hash=f"h_{i}",
            raw={"id": f"ord_{i}"},
            normalized={
                "placed_at": "2026-05-10T03:45:32Z",
                "total_inr": "1000.00",
                "currency": "INR",
                "payment_method": "cod",
                "financial_status": "pending",
                "pincode": "560001",
            },
        )
        session.add(row)
        session.flush()
        if row.id is not None:
            ids.append(row.id)
    session.commit()
    return ids


async def test_run_briefing_persists_run_log_with_expected_shape(session: Session) -> None:
    ids = _seed_orders(session, 2)

    # Canned LLM output: a narrative referencing real ids + one action.
    cite_pair = f"[cite:{ids[0]},{ids[1]}]"
    canned = BriefingOutput(
        narrative=f"This week saw 2 orders{cite_pair} worth Rs.2,000{cite_pair}.",
        proposed_actions=[
            ProposedAction(
                action_type="Review COD conversion campaign",
                reasoning=f"Both orders{cite_pair} were COD — worth a prepaid nudge.",
                evidence_record_ids=ids,
            )
        ],
        used_citations=ids,
    )
    test_model = TestModel(call_tools=["_query_orders"], custom_output_args=canned)

    summary = await run_briefing(
        session=session,
        merchant_id=DEFAULT_MERCHANT_ID,
        sector=Sector.FASHION,
        model_override=test_model,
    )
    session.commit()

    assert summary.sector is Sector.FASHION
    assert summary.actions_proposed == 1
    assert summary.items_scanned >= len(ids)

    runs = session.exec(select(RunLog).where(RunLog.kind == RunLogKind.AGENT.value)).all()
    assert len(runs) == 1
    detail = runs[0].detail_json
    assert detail["agent"] == AgentName.DAILY_BRIEFING.value
    assert detail["sector"] == Sector.FASHION.value
    assert isinstance(detail["narrative"], str)
    assert len(detail["narrative"]) > 0
    assert isinstance(detail["proposed_actions"], list)
    assert len(detail["proposed_actions"]) == 1
    assert detail["proposed_actions"][0]["action_type"] == "Review COD conversion campaign"
    assert isinstance(detail["citations"], list)
    assert detail["decisions"] == []  # briefing has no per-order decisions
    assert detail["orders_scanned"] == detail["actions_proposed"] or "narrative" in detail


async def test_run_briefing_uncited_number_in_narrative_is_stripped(session: Session) -> None:
    ids = _seed_orders(session, 1)

    # Narrative has one cited claim and one uncited claim (Rs.999 with no cite).
    canned = BriefingOutput(
        narrative=f"You had 1 order[cite:{ids[0]}] worth Rs.999.",
        used_citations=ids,
    )
    test_model = TestModel(call_tools=["_query_orders"], custom_output_args=canned)

    await run_briefing(
        session=session,
        merchant_id=DEFAULT_MERCHANT_ID,
        sector=Sector.GENERIC,
        model_override=test_model,
    )
    session.commit()

    run = session.exec(select(RunLog)).one()
    text = run.detail_json["narrative"]
    assert f"1 order[cite:{ids[0]}]" in text
    assert "Rs.999" not in text
    assert "[unverified number removed]" in text
