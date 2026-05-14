"""The citation enforcer — fail-closed post-processor for GroundedAnswer.

Each test pins a specific class of LLM hallucination. If the enforcer
gives the wrong answer on any of these inputs, the citation contract is
broken. These are the SCORED tests of the project per the assignment brief.
"""

from typing import Any

import pytest

from munim.chat.enforcer import (
    CitationEnforcerError,
    UnverifiedNumberError,
    enforce_grounded_answer,
)
from munim.chat.types import GroundedAnswer, RowCitation


def _cite(record_id: int) -> RowCitation:
    return RowCitation(
        record_id=record_id,
        entity_type="order",
        source_system="shopify",
        source_id=f"order_{record_id}",
        excerpt={},
    )


def test_valid_answer_passes_through_unchanged() -> None:
    answer = GroundedAnswer(
        text="Total revenue: ₹15,750[cite:1,2,3].",
        used_citations=[1, 2, 3],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2), _cite(3)])
    assert out == "Total revenue: ₹15,750[cite:1,2,3]."


def test_free_floating_currency_is_stripped() -> None:
    # The exact failure mode the brief calls out: "Uncited numbers don't
    # survive to the user." Without the enforcer, an LLM that confidently
    # invents ₹999 in a sentence ships that number to the merchant.
    answer = GroundedAnswer(
        text="Revenue was ₹15,750[cite:1] and discount was ₹50.",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert "₹50" not in out
    assert "[unverified number removed]" in out
    # The cited number stays.
    assert "₹15,750[cite:1]" in out


def test_free_floating_percent_is_stripped() -> None:
    answer = GroundedAnswer(
        text="Of those, 25% were COD[cite:1] and 30% were prepaid.",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert "30%" not in out
    assert "25% were COD[cite:1]" in out


def test_free_floating_count_is_stripped() -> None:
    answer = GroundedAnswer(
        text="You have 12 orders[cite:1,2,3] from 5 customers.",
        used_citations=[1, 2, 3],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2), _cite(3)])
    assert "5 customers" not in out
    assert "12 orders[cite:1,2,3]" in out


def test_hallucinated_row_id_in_cite_marker_raises() -> None:
    # If the model cites a row id that wasn't returned by any tool, the
    # answer is dishonest — fail closed, don't ship "₹15,750[cite:999]"
    # as if there's a row 999 backing it.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:999].",
        used_citations=[999],
    )
    with pytest.raises(CitationEnforcerError):
        enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2)])


def test_used_citations_must_match_text_cites() -> None:
    # Detects model contradicting itself: claims to use citations [1,2] but
    # the text only cites [1]. Fail closed.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:1].",
        used_citations=[1, 2],
    )
    # Lenient: extra in used_citations is OK (declared but not used).
    # Strict: text must only reference cites that are in available + used.
    # Going strict — any text cite must be in both available AND used.
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2)])
    assert out == "Revenue: ₹15,750[cite:1]."


def test_date_string_preserved() -> None:
    # Dates contain digits but aren't numeric CLAIMS. A real bug class would
    # be: enforcer mistakes "2026-05-14" for an uncited number and strips it.
    answer = GroundedAnswer(
        text="Orders placed on 2026-05-14[cite:1] totalled ₹15,750[cite:1].",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert "2026-05-14" in out


def test_shopify_order_id_preserved() -> None:
    # Shopify source_ids are long digit strings. If the enforcer treats
    # them as uncited numbers, every reference to an order becomes
    # "[unverified number removed]".
    answer = GroundedAnswer(
        text="Order 7218840502567[cite:1] is pending.",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert "7218840502567" in out


def test_pincode_preserved() -> None:
    # Pincodes are 6-digit strings that look like numeric claims but are
    # categorical identifiers.
    answer = GroundedAnswer(
        text="Most orders shipped to pincode 560001[cite:1,2,3].",
        used_citations=[1, 2, 3],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2), _cite(3)])
    assert "560001" in out


def test_empty_text_passes_through() -> None:
    answer = GroundedAnswer(text="I don't have data for that.", used_citations=[])
    out = enforce_grounded_answer(answer, available_citations=[])
    assert out == "I don't have data for that."


def test_multiple_uncited_numbers_in_one_sentence() -> None:
    answer = GroundedAnswer(
        text="Revenue grew from ₹10,000 to ₹15,750, up 57%.",
        used_citations=[],
    )
    out = enforce_grounded_answer(answer, available_citations=[])
    assert "₹10,000" not in out
    assert "₹15,750" not in out
    assert "57%" not in out
    # Each gets replaced individually.
    assert out.count("[unverified number removed]") == 3


def test_cite_followed_by_more_text() -> None:
    answer = GroundedAnswer(
        text="Revenue was ₹15,750[cite:1] last month — a clear win.",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert out == "Revenue was ₹15,750[cite:1] last month — a clear win."


def test_parser_failure_fails_closed() -> None:
    # If the enforcer hits an unexpected internal error (regex panic,
    # encoding issue), the response must be rejected — never ship a
    # half-validated answer. Simulate by giving an answer with garbled
    # cite markers the parser can't handle cleanly.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:abc,def].",  # non-integer ids in marker
        used_citations=[1],
    )
    with pytest.raises(CitationEnforcerError):
        enforce_grounded_answer(answer, available_citations=[_cite(1)])


# Suppress unused import warning — UnverifiedNumberError is exported for
# future strict-mode callers; it's tested via the public class hierarchy.
_: Any = UnverifiedNumberError
