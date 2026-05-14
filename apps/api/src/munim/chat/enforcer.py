"""Fail-closed citation post-processor.

Input: a `GroundedAnswer` from the LLM + the list of citations actually
returned by the tools the agent called.

Output: the answer's `text` with every numeric claim that's NOT inside a
"covered range" (the window before a `[cite:row_id,...]` marker) replaced
by `[unverified number removed]`. Raises `CitationEnforcerError` if the
answer is structurally dishonest: malformed cite marker, hallucinated row
id, used_citations referring to a row no tool returned, or text-cite that
isn't in used_citations.

Per docs/architecture.md §5.4: fail-closed by design. If we can't be
certain a number is grounded, we strip it. If the answer is internally
contradictory (text cites row not declared in used_citations, or
used_citations references a hallucinated row), we reject the whole answer.
"""

import re
from typing import Final

from munim.chat.types import GroundedAnswer, RowCitation
from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError

_CITE_MARKER = re.compile(r"\[cite:(?P<ids>[^\]]*)\]")

# Entity nouns that mark a number as a business claim requiring citation.
_ENTITY_NOUNS = (
    r"orders?|shipments?|customers?|products?|items?"
    r"|RTOs?|returns?|days?|hours?|rupees?|INR"
)

# Allow optional ASCII hyphen or Unicode minus (U+2212) at the start of a
# match so a stripped negative number doesn't leave a stray Unicode minus.
# Use the escape form so the source file passes ruff RUF001.
_NEG = "[-−]?"

# A numeric claim we consider must be cited:
#   - currency: ₹1,234, ₹1,234.56, Rs.99, $50 (with optional leading minus)
#   - percent: 25%, 25.5% (with optional leading minus)
#   - count + entity noun: "12 orders", "5 customers"
#   - Indian shortform: "1 lakh", "1.5 crore", "2 cr"
#   - bare comma-thousands: "1,234", "1,234.56"
#
# We deliberately DON'T flag:
#   - dates "2026-05-14" (no entity noun, no comma, no currency — no branch matches)
#   - times "10:42" / "10:42:30" (same — no branch matches)
#   - long bare IDs "7218840502567" (no commas, no entity noun, no currency — no branch matches)
#   - pincodes "560001" (6 digits, no entity noun, no currency, no comma — no branch matches)
#   - text inside [cite:...] markers (parsed first; their ranges become "covered")
#
# Currency / count+noun / comma-thousands branches all use the strict
# `\d{1,3}(?:,\d{3})*` form to avoid eating sentence commas like ", up".
_CLAIM_PATTERN = re.compile(
    r"""
    (?<!\d)                                            # not preceded by a digit
    (?:
        """
    + _NEG
    + r"""(?:₹|Rs\.?|\$)\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?    # currency
        |
        """
    + _NEG
    + r"""\d+(?:\.\d+)?\s*%                                # percent
        |
        """
    + _NEG
    + r"""\d{1,3}(?:,\d{3})*(?:\.\d+)?\s+(?:"""
    + _ENTITY_NOUNS
    + r""")\b                                              # count + entity noun
        |
        """
    + _NEG
    + r"""\d+(?:\.\d+)?\s*(?:lakhs?|crores?|cr)\b           # Indian shortform
        |
        """
    + _NEG
    + r"""\d{1,3}(?:,\d{3})+(?:\.\d+)?                     # comma-thousands
    )
    (?!\d)                                             # not followed by a digit
    """,
    re.VERBOSE | re.IGNORECASE,
)

# How far before a [cite:...] marker a numeric claim can appear and still
# be considered cited. 64 chars covers "12 orders worth ₹15,750[cite:...]"
# where both "12 orders" and "₹15,750" precede the same marker.
_PROXIMITY_CHARS: Final[int] = 64

_UNVERIFIED_SENTINEL: Final[str] = "[unverified number removed]"


class CitationEnforcerError(MunimError):
    """The answer cannot be honestly delivered. Fail closed; do not ship."""

    code = ErrorCode.CHAT_UNVERIFIED_ANSWER.value
    http_status = 502
    message = "Citation enforcer rejected the LLM's answer."


class UnverifiedNumberError(CitationEnforcerError):
    """Reserved for future strict modes that fail-close on a single uncited
    number rather than replacing. Currently the enforcer always REPLACES;
    this class exists so a strict caller can opt in later without changing
    the public surface.
    """

    message = "An uncited numeric claim was found."


def enforce_grounded_answer(
    answer: GroundedAnswer,
    available_citations: list[RowCitation],
) -> str:
    """Post-process a `GroundedAnswer`, returning the cleaned text.

    Raises `CitationEnforcerError` when:
    - A [cite:...] marker is malformed (non-integer ids) or empty.
    - A [cite:...] marker references a row id not in `available_citations`
      (the model hallucinated it).
    - `used_citations` references a row id not in `available_citations`
      (the model claims it used a row that no tool returned).
    - The text cites a row id not in `used_citations` (the model
      contradicts itself between text and metadata).

    Replaces (rather than raises) when:
    - A numeric claim appears in the text without a nearby [cite:...] marker.
    """
    available_ids = {c.record_id for c in available_citations}
    used_set = set(answer.used_citations)

    # --- 1. Cross-check: used_citations must be a subset of available_ids. ---
    hallucinated_in_used = used_set - available_ids
    if hallucinated_in_used:
        raise CitationEnforcerError(
            message=(
                f"used_citations references row(s) {sorted(hallucinated_in_used)} "
                "that no tool returned — the model hallucinated these ids."
            ),
            details={"hallucinated_in_used": sorted(hallucinated_in_used)},
        )

    # --- 2. Validate every [cite:...] marker, collect text-cited ids,
    #         build covered ranges. ---
    covered_ranges: list[tuple[int, int]] = []
    text_cite_ids: set[int] = set()
    for match in _CITE_MARKER.finditer(answer.text):
        ids_str = match.group("ids")
        try:
            cited_ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
        except ValueError as exc:
            raise CitationEnforcerError(
                message=f"Malformed cite marker: {match.group(0)!r} — ids must be integers.",
                details={"marker": match.group(0)},
            ) from exc
        if not cited_ids:
            raise CitationEnforcerError(
                message=f"Empty cite marker: {match.group(0)!r}.",
                details={"marker": match.group(0)},
            )
        for cid in cited_ids:
            if cid not in available_ids:
                raise CitationEnforcerError(
                    message=(
                        f"Text cite refers to row {cid} which was not returned by "
                        "any tool — the model hallucinated this id."
                    ),
                    details={"row_id": cid, "available": sorted(available_ids)},
                )
            text_cite_ids.add(cid)
        start = max(0, match.start() - _PROXIMITY_CHARS)
        covered_ranges.append((start, match.end()))

    # --- 3. Cross-check: every id in text cite markers must be in
    #         used_citations. (Extras in used_citations are tolerated —
    #         the model declared more than it used; harmless.) ---
    text_minus_used = text_cite_ids - used_set
    if text_minus_used:
        raise CitationEnforcerError(
            message=(
                f"Text cites row(s) {sorted(text_minus_used)} that are not in "
                "used_citations — the answer contradicts its own metadata."
            ),
            details={"in_text_not_in_used": sorted(text_minus_used)},
        )

    # --- 4. Scan for numeric claims; replace any outside covered ranges. ---
    out_parts: list[str] = []
    cursor = 0
    for claim in _CLAIM_PATTERN.finditer(answer.text):
        if cursor < claim.start():
            out_parts.append(answer.text[cursor : claim.start()])
        if _is_covered(claim.start(), claim.end(), covered_ranges):
            out_parts.append(claim.group(0))
        else:
            out_parts.append(_UNVERIFIED_SENTINEL)
        cursor = claim.end()
    if cursor < len(answer.text):
        out_parts.append(answer.text[cursor:])

    return "".join(out_parts)


def _is_covered(
    start: int,
    end: int,
    covered_ranges: list[tuple[int, int]],
) -> bool:
    """A claim is covered if its span is fully contained within any
    `(cite.start - _PROXIMITY_CHARS, cite.end)` range.
    """
    for cov_start, cov_end in covered_ranges:
        if cov_start <= start and end <= cov_end:
            return True
    return False
