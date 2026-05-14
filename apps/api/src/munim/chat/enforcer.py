"""Fail-closed citation post-processor.

Input: a `GroundedAnswer` from the LLM + the list of citations actually
returned by the tools the agent called.

Output: the answer's `text` with every numeric claim that's NOT immediately
followed by a `[cite:row_id,...]` marker replaced by `[unverified number
removed]`. Raises `CitationEnforcerError` if the answer is structurally
dishonest (hallucinated row ids, malformed cite markers, parser failure).

Per docs/architecture.md §5.4: the post-processor is fail-closed by design.
If we can't be certain a number is grounded, we strip it.
"""

import re
from typing import Final

from munim.chat.types import GroundedAnswer, RowCitation
from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError

_CITE_MARKER = re.compile(r"\[cite:(?P<ids>[^\]]*)\]")

# A "numeric claim" we consider must be cited:
#   - currency: ₹1,234, ₹1,234.56, Rs.99, $50
#   - percent: 25%, 25.5%
#   - count + entity noun: "12 orders", "5 customers"
#   - bare decimals/large numbers with commas: 1,234.56 (looks monetary)
# A "numeric claim" we DON'T flag:
#   - dates: 2026-05-14 (hyphen-separated) — excluded by lookbehind (?<![-/.])
#     and lookahead (?![-/:]) around separator chars
#   - times: 10:42:30 (colon-separated) — same mechanism
#   - long bare IDs: 7218840502567 — no comma, no decimal, no entity noun,
#     no currency prefix. The comma-thousands branch requires at least one
#     comma (`\d{1,3}(?:,\d{3})+`), so a bare 13-digit string is not matched.
#   - pincodes: 560001 — 6 digits, no entity noun, no currency, no comma →
#     not matched by any branch.
#   - numbers inside [cite:...] markers — excluded by parsing order (markers
#     are validated and their spans become "covered ranges" before we scan
#     for claims; the marker text itself is never re-scanned).
#
# Strategy:
#   1. Find every [cite:...] marker, parse the row ids inside, validate
#      they're all integers and that each id is in `available_citations`.
#      Raises CitationEnforcerError if either check fails.
#   2. Build a list of "covered ranges" — for each cite marker, the marker
#      itself plus the ~64 chars immediately preceding it (the numeric claim
#      it cites).
#   3. Find every numeric claim in the text via _CLAIM_PATTERN.
#   4. For each claim NOT inside a covered range, replace with the
#      "[unverified number removed]" sentinel.
# Entity nouns that mark a number as a business claim requiring citation.
# Split to a constant so the pattern line stays under the 100-char limit.
_ENTITY_NOUNS = (
    r"orders?|shipments?|customers?|products?|items?"
    r"|RTOs?|returns?|days?|hours?|rupees?|INR"
)

_CLAIM_PATTERN = re.compile(
    r"""
    (?<!\d)              # not preceded by a digit (avoid mid-ID matches)
    (?<![-/:.])          # not preceded by date/time/path separators
    (?:
        (?:₹|Rs\.?|\$)\s*\d[\d,]*(?:\.\d+)?   |  # currency: ₹1,234.56 / Rs.99 / $50
        \d+(?:\.\d+)?\s*%                       |  # percent: 25% / 25.5%
        \d[\d,]*(?:\.\d+)?\s+(?:"""
    + _ENTITY_NOUNS
    + r""")              |  # count + entity noun: "12 orders"
        \d{1,3}(?:,\d{3})+(?:\.\d+)?              # comma-thousands: 1,234 / 1,234.56
    )
    (?!\d)               # not followed by a digit (avoid mid-ID matches)
    (?![-/:])            # not followed by date/time separators
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
    """Raised internally when the enforcer would have to fail-close on a
    specific number. Currently we instead REPLACE — see implementation —
    but the class exists so future strict modes can fail entirely.
    """

    message = "An uncited numeric claim was found."


def enforce_grounded_answer(
    answer: GroundedAnswer,
    available_citations: list[RowCitation],
) -> str:
    """Post-process a `GroundedAnswer`, returning the cleaned text.

    Raises `CitationEnforcerError` when:
    - A [cite:...] marker contains non-integer ids (malformed).
    - A [cite:...] marker references a row id not in `available_citations`
      (hallucinated id).

    Replaces (rather than raises) when:
    - A numeric claim appears in the text without a nearby [cite:...] marker.
    """
    available_ids = {c.record_id for c in available_citations}

    # --- 1. Validate every [cite:...] marker. ---
    covered_ranges: list[tuple[int, int]] = []
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
                        f"Citation refers to row {cid} which was not returned by "
                        "any tool — the model hallucinated this id."
                    ),
                    details={"row_id": cid, "available": sorted(available_ids)},
                )
        # Mark a window from (marker_start - PROXIMITY_CHARS) to marker_end
        # as "covered" — any numeric claim inside this window is considered
        # cited by this marker.
        start = max(0, match.start() - _PROXIMITY_CHARS)
        covered_ranges.append((start, match.end()))

    # --- 2. Scan for numeric claims and replace any outside covered ranges. ---
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
    """A claim is covered if its span overlaps with a covered range
    (i.e., both the claim start and end fall within the pre-marker window
    plus the marker itself).
    """
    for cov_start, cov_end in covered_ranges:
        if cov_start <= start and end <= cov_end:
            return True
    return False
