"""Agent integration tests. We use PydanticAI's `TestModel` to mock the LLM
so tests don't hit the real OpenAI API. The TestModel returns a canned
`GroundedAnswer` after the agent's tool calls run.
"""

from datetime import UTC, datetime

import pytest
from pydantic_ai.models.test import TestModel
from sqlmodel import Session

from munim.chat.agent import answer_question
from munim.chat.tools import ChatContext
from munim.chat.types import GroundedAnswer
from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem

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


async def test_agent_returns_answered_question_with_cleaned_text(session: Session) -> None:
    # End-to-end: model returns a GroundedAnswer with one uncited number;
    # the service applies the enforcer; the final AnsweredQuestion has the
    # uncited number stripped.
    ids = _seed_orders(session, 3)
    ctx = ChatContext(merchant_id=DEFAULT_MERCHANT_ID, session=session)

    # TestModel returns this GroundedAnswer regardless of input.
    # call_tools=['_query_orders'] — we tell TestModel to call only the query
    # tool so we get real citations in the message history. The model's canned
    # output then references those real IDs, and the enforcer strips the
    # uncited ₹100.
    canned = GroundedAnswer(
        text=f"You have 3 orders[cite:{ids[0]},{ids[1]},{ids[2]}] with Rs.100 discount.",
        used_citations=ids,
    )
    test_model = TestModel(call_tools=["_query_orders"], custom_output_args=canned)

    result = await answer_question(
        question="How many orders do I have?",
        ctx=ctx,
        model_override=test_model,
    )
    # The cited "3 orders" stays; the uncited "Rs.100" is stripped.
    assert f"3 orders[cite:{ids[0]},{ids[1]},{ids[2]}]" in result.text
    assert "Rs.100" not in result.text
    assert "[unverified number removed]" in result.text
    # Citations passed through to the response.
    cited_ids = {c.record_id for c in result.citations}
    assert cited_ids == set(ids)


async def test_agent_rejects_answer_with_hallucinated_row_id(session: Session) -> None:
    _seed_orders(session, 2)
    ctx = ChatContext(merchant_id=DEFAULT_MERCHANT_ID, session=session)

    # Model cites a row id that wasn't returned by any tool — must fail.
    # call_tools=[] so no tool results enter available_citations; row 99999
    # is guaranteed absent from any real DB rows.
    canned = GroundedAnswer(
        text="Revenue: Rs.15750[cite:99999].",
        used_citations=[99999],
    )
    test_model = TestModel(call_tools=[], custom_output_args=canned)

    from munim.chat.enforcer import CitationEnforcerError

    with pytest.raises(CitationEnforcerError):
        await answer_question(
            question="What is my revenue?",
            ctx=ctx,
            model_override=test_model,
        )
