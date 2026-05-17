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


def test_used_citations_extras_are_tolerated() -> None:
    # Lenient direction: model declared used_citations=[1,2] but text only
    # cites [1]. Bookkeeping noise, not dishonesty — accept.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:1].",
        used_citations=[1, 2],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2)])
    assert out == "Revenue: ₹15,750[cite:1]."


def test_text_cite_missing_from_used_citations_is_tolerated() -> None:
    # The model cited row 2 in text but forgot to add it to its self-declared
    # used_citations. Row 2 IS in available_citations (a tool actually returned
    # it), so the real provenance check passes. used_citations is informational
    # only — the frontend renders from the full tool-returned set. Failing the
    # whole answer over this LLM-self-consistency mismatch is engineer-grade
    # strictness with no user-grade benefit.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:2].",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1), _cite(2)])
    assert out == "Revenue: ₹15,750[cite:2]."


def test_used_citations_referring_to_unavailable_row_raises() -> None:
    # Defense in depth: even if the text doesn't cite row 99, declaring
    # used_citations=[99] is the model claiming it used a row that no tool
    # returned. Fail closed before we even scan the text.
    answer = GroundedAnswer(
        text="Revenue: ₹15,750[cite:1].",
        used_citations=[1, 99],
    )
    with pytest.raises(CitationEnforcerError):
        enforce_grounded_answer(answer, available_citations=[_cite(1)])


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


def test_currency_does_not_eat_sentence_comma() -> None:
    # Phase 5 reviewer found this: with `\d[\d,]*`, the currency match was
    # greedily including the trailing sentence comma. "₹15,750, up 57%"
    # would match "₹15,750," (with comma) — the strip would also remove the
    # sentence comma, breaking grammar. Fixed by `\d{1,3}(?:,\d{3})*`.
    answer = GroundedAnswer(
        text="Revenue was ₹15,750, up sharply.",
        used_citations=[],
    )
    out = enforce_grounded_answer(answer, available_citations=[])
    # The currency is stripped, but the sentence comma stays put.
    assert "[unverified number removed], up sharply." in out


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


def test_unicode_minus_consumed_with_negative_percent() -> None:
    # Phase 5 reviewer caught this: when a negative percentage with Unicode
    # minus (U+2212, sometimes output by gpt-4o) is stripped, the minus
    # should go with the number — otherwise we leave a hanging minus and a
    # grammar-broken sentence. The fix is `[-−]?` at the start of the
    # percent branch. Source uses the escape form to pass ruff RUF001
    # (which flags ambiguous Unicode chars in literals).
    answer = GroundedAnswer(
        text="Growth was −15% this quarter.",
        used_citations=[],
    )
    out = enforce_grounded_answer(answer, available_citations=[])
    # Neither the number nor the minus survives — single sentinel replaces both.
    assert "15%" not in out
    assert "−" not in out
    assert "[unverified number removed]" in out


def test_indian_lakh_form_is_flagged_as_uncited() -> None:
    # "1 lakh", "1.5 crore", "2 cr" are the most natural way an Indian
    # D2C model expresses large numbers. Without the lakhs/crore branch,
    # "Revenue was 1.5 cr" would pass through the enforcer unflagged —
    # a hallucinated big number ships to the merchant.
    answer = GroundedAnswer(
        text="Revenue was 1.5 cr this month.",
        used_citations=[],
    )
    out = enforce_grounded_answer(answer, available_citations=[])
    assert "1.5 cr" not in out
    assert "[unverified number removed]" in out


def test_indian_lakh_word_form_is_flagged() -> None:
    answer = GroundedAnswer(
        text="You have 1 lakh customers.",
        used_citations=[],
    )
    out = enforce_grounded_answer(answer, available_citations=[])
    assert "1 lakh" not in out


def test_cited_lakh_form_passes_through() -> None:
    # Cited Indian shortform stays intact.
    answer = GroundedAnswer(
        text="Revenue was 1.5 cr[cite:1] this month.",
        used_citations=[1],
    )
    out = enforce_grounded_answer(answer, available_citations=[_cite(1)])
    assert "1.5 cr[cite:1]" in out


# Suppress unused import warning — UnverifiedNumberError is exported for
# future strict-mode callers; it's tested via the public class hierarchy.
_: Any = UnverifiedNumberError
