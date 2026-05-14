"""Citation types — the shape every chat tool returns and the model is forced into."""

from typing import Any

import pytest
from pydantic import ValidationError

from munim.chat.types import (
    AnsweredQuestion,
    GroundedAnswer,
    RowCitation,
    ToolResult,
)


def _make_citation(record_id: int = 42) -> RowCitation:
    return RowCitation(
        record_id=record_id,
        entity_type="order",
        source_system="shopify",
        source_id="7218840502567",
        excerpt={"placed_at": "2026-05-10T03:45:32Z", "total_inr": "1249.00"},
    )


def test_row_citation_round_trip() -> None:
    c = _make_citation()
    rebuilt = RowCitation.model_validate(c.model_dump(mode="json"))
    assert rebuilt == c


def test_row_citation_forbids_extra_fields() -> None:
    # An LLM that hallucinates a `confidence` field on a citation must fail
    # to construct, not silently store the extra. Same convention as every
    # other public Pydantic surface (Phase 2 review lesson).
    with pytest.raises(ValidationError):
        RowCitation(  # type: ignore[call-arg]
            record_id=1,
            entity_type="order",
            source_system="shopify",
            source_id="x",
            excerpt={},
            confidence=0.9,
        )


def test_tool_result_carries_data_and_citations() -> None:
    payload: dict[str, Any] = {"orders": [{"id": "x", "total": "1.00"}]}
    result: ToolResult[dict[str, Any]] = ToolResult(
        data=payload,
        citations=[_make_citation(1), _make_citation(2)],
    )
    assert len(result.citations) == 2
    assert result.citations[0].record_id == 1


def test_grounded_answer_round_trip() -> None:
    ga = GroundedAnswer(
        text="Total revenue this month: ₹15,750[cite:1,2,3].",
        used_citations=[1, 2, 3],
    )
    rebuilt = GroundedAnswer.model_validate(ga.model_dump(mode="json"))
    assert rebuilt == ga


def test_grounded_answer_used_citations_must_be_ints() -> None:
    # The LLM might emit "1, 2, 3" as a string. Pydantic must reject —
    # ints in a list, not a comma-separated string. Catches one class
    # of model misformatting that the enforcer can't downstream-fix.
    with pytest.raises(ValidationError):
        GroundedAnswer.model_validate({"text": "...", "used_citations": "1, 2, 3"})


def test_answered_question_packages_text_plus_citations_for_response() -> None:
    aq = AnsweredQuestion(
        text="Total revenue: ₹15,750[cite:1].",
        citations=[_make_citation(1)],
    )
    payload = aq.model_dump(mode="json")
    assert payload["text"] == "Total revenue: ₹15,750[cite:1]."
    assert payload["citations"][0]["record_id"] == 1
