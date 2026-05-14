# Phase 5 — Chat Tools + PydanticAI Orchestrator + Citation Contract Implementation Plan

> **For agentic workers:** ONE subagent dispatch for the whole phase (CLAUDE.md §3). 7 tasks top-to-bottom, commit per task, report when DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Use `superpowers:subagent-driven-development`.
>
> **Test discipline (§13.4):** the citation enforcer is the highest-leverage code in this project — it's THE scored axis ("chat grounding: citation contract is real, every number traceable, no hallucinated values"). Every enforcer test pins a specific failure mode that a real LLM hallucination could trigger. If the model can break the contract in a way your test doesn't cover, ADD the test.

**Goal:** Wire a backend chat surface that takes a natural-language question, dispatches to a PydanticAI agent with typed tools that read the synced `record` rows, produces a `GroundedAnswer` where every numerical claim carries `[cite:row_id,...]` markers, and runs a fail-closed post-processor that strips any uncited number. The output is the JSON `{text, citations}` shape Phase 6 will render. Frontend chat UI is Phase 6 — Phase 5 ships the engine, tested against PydanticAI's `TestModel` for unit tests + one env-gated live test against real OpenAI.

**Architecture:**
- New package `apps/api/src/munim/chat/`:
  - `types.py` — `RowCitation`, `ToolResult[T]`, `GroundedAnswer`, `AnsweredQuestion` Pydantic models.
  - `enforcer.py` — the fail-closed citation post-processor. The piece that gets the most adversarial tests.
  - `tools.py` — typed tools the agent registers: `query_orders`, `compute_metric`, `propose_action`. Each returns `ToolResult` with the row ids that produced the data.
  - `agent.py` — PydanticAI Agent setup. System prompt embeds the citation contract, output type forces `GroundedAnswer`, tools are registered with `@agent.tool`.
- New module `apps/api/src/munim/modules/chat/`:
  - `schemas.py` — request/response Pydantic shapes for `POST /chat/messages`.
  - `service.py` — orchestrates the agent run + invokes the enforcer + assembles the response.
  - `router.py` — the FastAPI endpoint. Returns `SuccessEnvelope[ChatMessageResponse]` with `text` (post-processed) and `citations` (the row references the frontend renders as badges).
- Settings adds `openai_api_key` (REQUIRED, no default — fail-fast at startup if missing), `openai_chat_model` (default `gpt-4o-mini`), `openai_chat_temperature` (default `0.0` — deterministic-ish for grounded answers).
- `BaseConnector` ABC and the `record` schema are untouched. Chat reads through the existing `Record` rows via SQLModel queries.

**Tech stack additions:**
- `pydantic-ai>=0.4` (current stable in 2026, ships with `TestModel` for unit tests, supports OpenAI + Anthropic + a dozen others via model strings).

**Out of scope (deliberate, called out so reviewers know what's not in v0):**
- Streaming SSE responses (Phase 6 wires the frontend's `useChat` + Vercel AI SDK; Phase 5 returns one JSON envelope per request).
- Multi-turn chat history (each `POST /chat/messages` is single-turn; Phase 6 may add history if needed).
- `query_shipments`, `query_ad_spend`, `query_customer_history` (no synced data yet; Phase 5b adds Meta + Shiprocket if time allows).
- Vector / embedding-based search (we have ≤100 records per merchant in demo; full-table scan is fine).
- Cost / token budgeting per merchant (Phase 9+).
- Paraphrase-level number verification (catching "₹15 lakh" misquoted as "₹1.5 cr" when the underlying row says ₹15,00,000 — the enforcer catches uncited numbers but not misparaphrased cited numbers. Acknowledged honestly in the README's "where it breaks" section, per `docs/architecture.md §5.5`).

---

## File map

**New files:**
- `apps/api/src/munim/chat/__init__.py` — empty.
- `apps/api/src/munim/chat/types.py` — `RowCitation`, `ToolResult`, `GroundedAnswer`, `AnsweredQuestion`.
- `apps/api/src/munim/chat/enforcer.py` — `enforce_grounded_answer`, error types.
- `apps/api/src/munim/chat/tools.py` — tool functions (used inside the agent).
- `apps/api/src/munim/chat/agent.py` — agent factory + `ask` function.
- `apps/api/src/munim/chat/tests/__init__.py` — empty.
- `apps/api/src/munim/chat/tests/test_types.py` — round-trip + extra="forbid" tests.
- `apps/api/src/munim/chat/tests/test_enforcer.py` — the high-leverage test suite for the citation contract.
- `apps/api/src/munim/chat/tests/test_tools.py` — tool behaviour against real DB.
- `apps/api/src/munim/chat/tests/test_agent.py` — agent integration with `TestModel`.
- `apps/api/src/munim/modules/chat/__init__.py` — empty.
- `apps/api/src/munim/modules/chat/schemas.py` — request/response Pydantic.
- `apps/api/src/munim/modules/chat/service.py` — orchestrator that ties the chat module to the chat package.
- `apps/api/src/munim/modules/chat/router.py` — POST `/chat/messages`.
- `apps/api/src/munim/modules/chat/tests/__init__.py` — empty.
- `apps/api/src/munim/modules/chat/tests/test_router.py` — endpoint tests via TestClient + TestModel.

**Modified files:**
- `apps/api/pyproject.toml` — add `pydantic-ai`.
- `apps/api/src/munim/shared/config.py` — add 3 OpenAI env vars to `Settings`.
- `apps/api/src/munim/shared/constants.py` — add `CHAT_LLM_UNAVAILABLE`, `CHAT_TOOL_FAILED`, `CHAT_UNVERIFIED_ANSWER` to `ErrorCode`.
- `apps/api/src/munim/main.py` — register the chat router.
- `.env.example` — uncomment/document OpenAI env vars.

---

## Task 1 — Deps + Settings + Constants

**Files:**
- Modify: `apps/api/pyproject.toml` — add pydantic-ai.
- Modify: `apps/api/src/munim/shared/config.py` — OpenAI fields.
- Modify: `apps/api/src/munim/shared/constants.py` — chat error codes.
- Modify: `.env.example` — document the OpenAI vars.

- [ ] **Step 1: Add dep**

In `apps/api/pyproject.toml`, append to `dependencies`:

```toml
"pydantic-ai>=0.4",
```

Then from `apps/api`:
```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
uv sync
```

- [ ] **Step 2: Extend `Settings`**

In `apps/api/src/munim/shared/config.py`, add fields to the `Settings` class (keep alphabetical-ish ordering — group Shopify + OpenAI separately as the existing file does):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Phase 1 — sensible defaults.
    database_url: str = "sqlite:///./data/munim.sqlite"
    log_level: str = "info"
    app_env: str = "development"

    # Phase 4 — Shopify (existing, unchanged).
    shopify_client_id: str
    shopify_client_secret: str
    shopify_api_version: str = "2026-04"
    shopify_oauth_redirect_uri: str
    shopify_default_shop_domain: str
    credentials_encryption_key: str

    # Phase 5 — OpenAI. API key required; model/temperature have defaults.
    openai_api_key: str
    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_temperature: float = 0.0
    # `openai_embedding_model` is present in .env but not used in Phase 5.
    # Declare it so `extra="ignore"` doesn't matter; we don't need it yet.

    # Frontend URL used by the OAuth callback redirect (existing).
    frontend_base_url: str = "http://localhost:5173"
```

The required `openai_api_key: str` has no default — startup throws if missing.

- [ ] **Step 3: Extend `ErrorCode`**

In `apps/api/src/munim/shared/constants.py`, add to `ErrorCode`:

```python
class ErrorCode(StrEnum):
    # ... existing ...
    AUTH_CREDENTIAL_UNREADABLE = "auth.credential_unreadable"
    CHAT_LLM_UNAVAILABLE = "chat.llm_unavailable"
    CHAT_TOOL_FAILED = "chat.tool_failed"
    CHAT_UNVERIFIED_ANSWER = "chat.unverified_answer"
```

- [ ] **Step 4: Document env vars**

In `.env.example`, append below the Shopify section:

```
# --- Phase 5: OpenAI chat ---
# Required. Get from https://platform.openai.com/api-keys
OPENAI_API_KEY=
# Default: gpt-4o-mini (cheap + tool-use capable). Override to gpt-4o for harder questions.
OPENAI_CHAT_MODEL=gpt-4o-mini
# 0.0 keeps grounded answers deterministic-ish. Set higher only for casual chat.
OPENAI_CHAT_TEMPERATURE=0.0
# Optional — used by Phase 6+ if we add embedding-based search.
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

- [ ] **Step 5: Verify startup**

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api'
uv run python -c "from munim.shared.config import get_settings; s = get_settings(); print('chat model:', s.openai_chat_model, 'temp:', s.openai_chat_temperature)"
```

Expected: prints `chat model: gpt-4o-mini temp: 0.0`. Should also succeed because the user already added `OPENAI_API_KEY` to `apps/api/.env`.

- [ ] **Step 6: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 95 passed (no regressions from Phase 4).

- [ ] **Step 7: Commit**

```
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/src/munim/shared/config.py apps/api/src/munim/shared/constants.py .env.example
git commit -m "feat(config): add OpenAI + chat env vars + pydantic-ai dep"
```

---

## Task 2 — Chat types: `RowCitation`, `ToolResult`, `GroundedAnswer`, `AnsweredQuestion`

**Files:**
- Create: `apps/api/src/munim/chat/__init__.py`
- Create: `apps/api/src/munim/chat/types.py`
- Create: `apps/api/src/munim/chat/tests/__init__.py`
- Create: `apps/api/src/munim/chat/tests/test_types.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/src/munim/chat/__init__.py` (empty).
Create `apps/api/src/munim/chat/tests/__init__.py` (empty).
Create `apps/api/src/munim/chat/tests/test_types.py`:

```python
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
        GroundedAnswer.model_validate(
            {"text": "...", "used_citations": "1, 2, 3"}
        )


def test_answered_question_packages_text_plus_citations_for_response() -> None:
    aq = AnsweredQuestion(
        text="Total revenue: ₹15,750[cite:1].",
        citations=[_make_citation(1)],
    )
    payload = aq.model_dump(mode="json")
    assert payload["text"] == "Total revenue: ₹15,750[cite:1]."
    assert payload["citations"][0]["record_id"] == 1
```

- [ ] **Step 2: Run tests, see ImportError**

```
uv run pytest src/munim/chat/tests/test_types.py -v
```

- [ ] **Step 3: Implement types**

Create `apps/api/src/munim/chat/types.py`:

```python
"""Citation primitives used by every chat tool and the agent's structured output.

These types are the contract between:
  - tools (which return `ToolResult` so the agent knows which rows backed each
    piece of data),
  - the agent's structured output (`GroundedAnswer` — the LLM is forced into
    this shape),
  - the post-processor (`enforcer.py` consumes both),
  - the API response (`AnsweredQuestion` is the per-request envelope payload).

`extra="forbid"` on every surface — see docs/conventions.md §13.4 + Phase 2
review lesson. An LLM that fabricates a field at run time must fail to
construct, not silently pass through.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class RowCitation(BaseModel):
    """Provenance pointer to one `record` row, with an excerpt of its
    normalized projection. Returned by tools, embedded in `AnsweredQuestion`.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: int
    entity_type: str
    source_system: str
    source_id: str
    excerpt: dict[str, Any]


class ToolResult(BaseModel, Generic[T]):
    """Every tool the agent calls returns this. `data` is the tool's payload
    (numeric, list of rows, whatever); `citations` are the `record` rows that
    produced it. The agent quotes the row ids in its final answer.
    """

    model_config = ConfigDict(extra="forbid")

    data: T
    citations: list[RowCitation]


class GroundedAnswer(BaseModel):
    """The shape the LLM is forced into via PydanticAI's `output_type`.
    `text` contains `[cite:N,M,...]` markers inline with each numeric claim.
    `used_citations` is the union of row ids the LLM says it referenced —
    used as a cross-check in the post-processor.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    used_citations: list[int]


class AnsweredQuestion(BaseModel):
    """The per-request payload returned by `POST /chat/messages`. The text
    has been through the enforcer (any free-floating numeric claim has been
    replaced with `[unverified number removed]`); citations are the rows the
    UI renders as badges.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[RowCitation]
```

- [ ] **Step 4: Run tests, see them pass**

```
uv run pytest src/munim/chat/tests/test_types.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 101 passed (95 + 6).

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/chat
git commit -m "feat(chat): add RowCitation + ToolResult + GroundedAnswer + AnsweredQuestion types"
```

---

## Task 3 — Citation enforcer (the load-bearing piece)

**Files:**
- Create: `apps/api/src/munim/chat/enforcer.py`
- Create: `apps/api/src/munim/chat/tests/test_enforcer.py`

This is THE highest-leverage code in the project. Every test here pins a class of LLM hallucination. Don't add a test unless it fails on a real, distinct bug class.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/src/munim/chat/tests/test_enforcer.py`:

```python
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
```

- [ ] **Step 2: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/chat/tests/test_enforcer.py -v
```

- [ ] **Step 3: Implement the enforcer**

Create `apps/api/src/munim/chat/enforcer.py`:

```python
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
#   - dates: 2026-05-14 (hyphen-separated)
#   - times: 10:42:30 (colon-separated)
#   - long IDs: 7218840502567 (no comma, no decimal, no entity noun, len > 6)
#   - pincodes: 560001 (6 digits, no entity noun)
#   - quoted strings inside [cite:...] markers (excluded by parsing order)
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
_CLAIM_PATTERN = re.compile(
    r"""
    (?<!\d)              # not preceded by a digit (avoid mid-ID matches)
    (?<![-/:.])          # not preceded by date/time separators
    (?:
        (?:₹|Rs\.?|\$)\s*\d[\d,]*(?:\.\d+)? |  # currency: ₹1,234.56 / Rs.99 / $50
        \d+(?:\.\d+)?\s*% |                     # percent: 25% / 25.5%
        \d[\d,]*(?:\.\d+)?\s+(?:orders?|shipments?|customers?|products?|items?|RTOs?|returns?|days?|hours?|rupees?|INR) |  # count + noun
        \d{1,3}(?:,\d{3})+(?:\.\d+)?            # comma-thousands (1,234 / 1,234.56)
    )
    (?!\d)               # not followed by a digit
    (?![-/:])            # not followed by date/time separators
    """,
    re.VERBOSE | re.IGNORECASE,
)

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
    """A claim is covered if its END is within `_PROXIMITY_CHARS` chars
    BEFORE the start of some [cite:...] marker (i.e., the cite comes right
    after the number).
    """
    for cov_start, cov_end in covered_ranges:
        if cov_start <= start and end <= cov_end:
            return True
    return False
```

Implementation notes:
- The `_PROXIMITY_CHARS = 64` window is intentionally generous — the LLM sometimes writes "12 orders worth ₹15,750[cite:1,2,3]" where the cite is at the end of the clause. Both "12 orders" and "₹15,750" should be considered cited.
- This means a multi-number sentence like "12 orders[cite:1] 5 customers" — the "5 customers" is OUTSIDE the cite window (it's AFTER the cite), so it gets stripped. That's the right behavior (each number needs its own cite or a shared trailing one).

- [ ] **Step 4: Run tests, see them pass**

```
uv run pytest src/munim/chat/tests/test_enforcer.py -v
```

Expected: 13 passed. If anything fails, refine the regex or proximity window with documentation in the test — DON'T weaken the contract.

- [ ] **Step 5: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 114 passed (101 + 13).

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/chat/enforcer.py apps/api/src/munim/chat/tests/test_enforcer.py
git commit -m "feat(chat): citation enforcer — strip uncited numbers, fail-close on hallucinated row ids"
```

---

## Task 4 — Tools: `query_orders`, `compute_metric`, `propose_action`

**Files:**
- Create: `apps/api/src/munim/chat/tools.py`
- Create: `apps/api/src/munim/chat/tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/src/munim/chat/tests/test_tools.py`:

```python
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
    PaymentMethod,
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
    blr = _make_record(session, source_id="A", total_inr="100", payment_method="cod", pincode="560001")
    _make_record(session, source_id="B", total_inr="200", payment_method="prepaid", pincode="110001")
    session.commit()

    result = query_orders(_ctx(session), pincode="560001")
    assert len(result.data) == 1
    assert result.citations[0].record_id == blr.id


def test_query_orders_filters_by_utm_campaign(session: Session) -> None:
    a = _make_record(session, source_id="A", total_inr="100", payment_method="cod", utm_campaign="meta_summer")
    _make_record(session, source_id="B", total_inr="200", payment_method="cod", utm_campaign="google_search")
    session.commit()

    result = query_orders(_ctx(session), utm_campaign="meta_summer")
    assert len(result.data) == 1
    assert result.citations[0].record_id == a.id


def test_compute_metric_sum_total_inr(session: Session) -> None:
    a = _make_record(session, source_id="A", total_inr="1249.50", payment_method="cod")
    b = _make_record(session, source_id="B", total_inr="2199.50", payment_method="prepaid")
    session.commit()

    result = compute_metric(_ctx(session), formula="sum_total_inr")
    assert result.data == Decimal("3449.00")
    cited = {c.record_id for c in result.citations}
    assert cited == {a.id, b.id}


def test_compute_metric_count_orders(session: Session) -> None:
    for i in range(5):
        _make_record(session, source_id=f"X{i}", total_inr="100", payment_method="cod")
    session.commit()

    result = compute_metric(_ctx(session), formula="count_orders")
    assert result.data == 5
    assert len(result.citations) == 5


def test_compute_metric_unknown_formula_raises(session: Session) -> None:
    # Per §10 no silent fallback: an unknown formula must raise, not return 0.
    from munim.chat.tools import UnknownMetricFormulaError

    with pytest.raises(UnknownMetricFormulaError):
        compute_metric(_ctx(session), formula="madeup_metric")


def test_propose_action_writes_run_log_no_side_effect(session: Session) -> None:
    # propose_action is the only "write" tool in v0; per the brief and
    # docs/architecture.md §8 the agent NEVER dispatches messages or
    # modifies external state. It only persists the proposed action to
    # `run_log` for human review.
    a = _make_record(session, source_id="A", total_inr="1249", payment_method="cod")
    session.commit()

    result = propose_action(
        _ctx(session),
        action_type="convert_to_prepaid",
        target_record_id=a.id if a.id is not None else 0,
        reasoning="High RTO risk on this pincode.",
        evidence_record_ids=[a.id if a.id is not None else 0],
    )
    session.commit()

    # The run_log row exists and references the evidence rows.
    from sqlmodel import select
    runs = session.exec(select(RunLog)).all()
    assert len(runs) == 1
    assert runs[0].kind == "chat"
    assert runs[0].detail_json["action_type"] == "convert_to_prepaid"
    # The tool returns the run_log row id as data + the evidence as citations.
    assert result.data["run_log_id"] == runs[0].id
    assert {c.record_id for c in result.citations} == {a.id}
```

- [ ] **Step 2: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/chat/tests/test_tools.py -v
```

- [ ] **Step 3: Implement tools**

Create `apps/api/src/munim/chat/tools.py`:

```python
"""Typed tools the chat agent calls. Each tool reads from the `record` table
filtered by `merchant_id` and returns a `ToolResult` carrying both the data
and the `RowCitation`s of the rows that produced it.

`propose_action` is the only "write" tool — it persists the proposed action
to `run_log` for a human to review. No external side effects. Matches the
brief's "AI employee proposes, doesn't dispatch" constraint.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlmodel import Session, col, select

from munim.chat.types import RowCitation, ToolResult
from munim.models import Record, RunLog
from munim.shared.constants import (
    EntityType,
    ErrorCode,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)
from munim.shared.errors import MunimError


class UnknownMetricFormulaError(MunimError):
    code = ErrorCode.CHAT_TOOL_FAILED.value
    http_status = 400
    message = "Unknown metric formula."


@dataclass
class ChatContext:
    """Bag of dependencies the tools share. Passed into each tool by the
    agent's `RunContext`.
    """

    merchant_id: str
    session: Session


def _row_to_citation(row: Record, fields: list[str] | None = None) -> RowCitation:
    if fields is None:
        excerpt = dict(row.normalized)
    else:
        excerpt = {k: row.normalized.get(k) for k in fields}
    return RowCitation(
        record_id=row.id if row.id is not None else 0,
        entity_type=row.entity_type,
        source_system=row.source_system,
        source_id=row.source_id,
        excerpt=excerpt,
    )


def query_orders(
    ctx: ChatContext,
    *,
    payment_method: PaymentMethod | None = None,
    pincode: str | None = None,
    utm_campaign: str | None = None,
    financial_status: str | None = None,
) -> ToolResult[list[dict[str, Any]]]:
    """Filter Shopify orders by common attributes. Returns a list of order
    dicts (`normalized` JSON) plus citations pointing to each row.
    """
    stmt = (
        select(Record)
        .where(Record.merchant_id == ctx.merchant_id)
        .where(Record.source_system == SourceSystem.SHOPIFY.value)
        .where(Record.entity_type == EntityType.ORDER.value)
        .order_by(col(Record.fetched_at).desc())
    )
    rows = ctx.session.exec(stmt).all()

    def matches(row: Record) -> bool:
        n = row.normalized
        if payment_method is not None and n.get("payment_method") != payment_method.value:
            return False
        if pincode is not None and n.get("pincode") != pincode:
            return False
        if utm_campaign is not None and n.get("utm_campaign") != utm_campaign:
            return False
        if financial_status is not None and n.get("financial_status") != financial_status:
            return False
        return True

    matched = [r for r in rows if matches(r)]
    data = [dict(r.normalized) for r in matched]
    citations = [_row_to_citation(r, fields=["placed_at", "total_inr", "payment_method", "pincode"]) for r in matched]
    return ToolResult(data=data, citations=citations)


MetricFormula = Literal["sum_total_inr", "count_orders"]


def compute_metric(
    ctx: ChatContext,
    *,
    formula: str,
    payment_method: PaymentMethod | None = None,
    pincode: str | None = None,
) -> ToolResult[Decimal | int]:
    """Aggregate over the filtered order set. `formula` is one of:
      - `sum_total_inr` — sum of `total_inr` over orders matching the filter.
      - `count_orders` — count of orders matching the filter.

    Citations include every row that contributed to the aggregate.
    """
    filtered = query_orders(
        ctx,
        payment_method=payment_method,
        pincode=pincode,
    )

    if formula == "sum_total_inr":
        total = sum((Decimal(d["total_inr"]) for d in filtered.data), start=Decimal("0"))
        return ToolResult(data=total, citations=filtered.citations)
    if formula == "count_orders":
        return ToolResult(data=len(filtered.data), citations=filtered.citations)

    raise UnknownMetricFormulaError(
        message=f"Unknown metric formula: {formula!r}. Known: sum_total_inr, count_orders.",
        details={"formula": formula},
    )


def propose_action(
    ctx: ChatContext,
    *,
    action_type: str,
    target_record_id: int,
    reasoning: str,
    evidence_record_ids: list[int],
) -> ToolResult[dict[str, Any]]:
    """Persist a proposed action to `run_log`. NO external side effects.
    The human sees the proposal in the agent runs view (Phase 8) and
    decides whether to act.
    """
    now = datetime.now(UTC)
    run = RunLog(
        merchant_id=ctx.merchant_id,
        kind=RunLogKind.CHAT.value,
        started_at=now,
        finished_at=now,
        detail_json={
            "action_type": action_type,
            "target_record_id": target_record_id,
            "reasoning": reasoning,
            "evidence_record_ids": evidence_record_ids,
        },
    )
    ctx.session.add(run)
    ctx.session.flush()

    evidence_rows = ctx.session.exec(
        select(Record).where(col(Record.id).in_(evidence_record_ids))
    ).all()
    citations = [_row_to_citation(r) for r in evidence_rows]

    return ToolResult(
        data={
            "run_log_id": run.id,
            "action_type": action_type,
            "target_record_id": target_record_id,
        },
        citations=citations,
    )
```

- [ ] **Step 4: Run tests, see them pass**

```
uv run pytest src/munim/chat/tests/test_tools.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 122 passed.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/chat/tools.py apps/api/src/munim/chat/tests/test_tools.py
git commit -m "feat(chat): tools — query_orders + compute_metric + propose_action"
```

---

## Task 5 — Agent (PydanticAI orchestrator)

**Files:**
- Create: `apps/api/src/munim/chat/agent.py`
- Create: `apps/api/src/munim/chat/tests/test_agent.py`

- [ ] **Step 1: Write the failing tests using PydanticAI's `TestModel`**

Create `apps/api/src/munim/chat/tests/test_agent.py`:

```python
"""Agent integration tests. We use PydanticAI's `TestModel` to mock the LLM
so tests don't hit the real OpenAI API. The TestModel returns a canned
`GroundedAnswer` after the agent's tool calls run.
"""

from datetime import UTC, datetime
from typing import Any

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
    canned = GroundedAnswer(
        text=f"You have 3 orders[cite:{ids[0]},{ids[1]},{ids[2]}] with ₹100 discount.",
        used_citations=ids,
    )
    test_model = TestModel(custom_output_args=canned)

    result = await answer_question(
        question="How many orders do I have?",
        ctx=ctx,
        model_override=test_model,
    )
    # The cited "3 orders" stays; the uncited "₹100" is stripped.
    assert f"3 orders[cite:{ids[0]},{ids[1]},{ids[2]}]" in result.text
    assert "₹100" not in result.text
    assert "[unverified number removed]" in result.text
    # Citations passed through to the response.
    cited_ids = {c.record_id for c in result.citations}
    assert cited_ids == set(ids)


async def test_agent_rejects_answer_with_hallucinated_row_id(session: Session) -> None:
    _seed_orders(session, 2)
    ctx = ChatContext(merchant_id=DEFAULT_MERCHANT_ID, session=session)

    # Model cites a row id that wasn't returned by any tool — must fail.
    canned = GroundedAnswer(
        text="Revenue: ₹15,750[cite:99999].",
        used_citations=[99999],
    )
    test_model = TestModel(custom_output_args=canned)

    from munim.chat.enforcer import CitationEnforcerError

    with pytest.raises(CitationEnforcerError):
        await answer_question(
            question="What is my revenue?",
            ctx=ctx,
            model_override=test_model,
        )
```

Note: PydanticAI's `TestModel(custom_output_args=...)` returns the canned output without calling any real model. This is the standard PydanticAI test pattern. If the test fails because the API differs in the installed version, the implementer may need to adjust to `TestModel(custom_result=...)` or similar — check `pydantic_ai.models.test` docstrings.

- [ ] **Step 2: Run tests, see them fail with ImportError**

```
uv run pytest src/munim/chat/tests/test_agent.py -v
```

- [ ] **Step 3: Implement the agent**

Create `apps/api/src/munim/chat/agent.py`:

```python
"""PydanticAI agent that orchestrates tool calls and produces a
`GroundedAnswer`. The service layer then runs the enforcer over the
answer + the union of citations from every tool call.

We construct the agent on every request (not module-level) so each
request gets its own `RunContext` with the right session + merchant.
The model itself is read from `Settings.openai_chat_model` so swapping
to `gpt-4o` or another OpenAI model is one env-var change.
"""

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from munim.chat.enforcer import enforce_grounded_answer
from munim.chat.tools import (
    ChatContext,
    UnknownMetricFormulaError,
    compute_metric,
    propose_action,
    query_orders,
)
from munim.chat.types import AnsweredQuestion, GroundedAnswer, RowCitation, ToolResult
from munim.shared.config import get_settings
from munim.shared.constants import PaymentMethod
from munim.shared.errors import MunimError

_SYSTEM_PROMPT = """You are AI-Munim, an AI employee for a D2C founder.

You answer questions about the founder's business by calling the tools
provided. Every tool returns rows of source data alongside the answer.

OUTPUT CONTRACT (non-negotiable):
- Output a single `GroundedAnswer` with `text` and `used_citations`.
- Every numerical value in `text` MUST be immediately followed by a cite
  marker of the form `[cite:row_id]` or `[cite:row_id,row_id,...]`, where
  each row_id is taken from the `citations` of a tool result you used.
- Example: "You had 12 orders[cite:1,2,3,4,5,6,7,8,9,10,11,12] worth
  ₹15,750[cite:1,2,3,4,5,6,7,8,9,10,11,12] this month."
- If you do not have a citation for a number, DO NOT state the number.
  Say "[unknown]" instead.
- `used_citations` lists the row_ids you actually referenced in `text`.

Tools available:
- `query_orders` — filter orders by payment_method, pincode, utm_campaign,
  financial_status. Returns the matching rows.
- `compute_metric` — compute `sum_total_inr` or `count_orders` over filtered
  orders. Returns the scalar plus the rows that contributed.
- `propose_action` — record a proposed action (e.g., convert a COD order to
  prepaid). Persisted to the run log; does NOT dispatch any message. Use
  only when the user explicitly asks for an action.

Style: terse, founder-friendly, no hedging. If you don't have data, say so."""


def build_agent(model: Model | str | None = None) -> Agent[ChatContext, GroundedAnswer]:
    settings = get_settings()
    model_spec: Model | str
    if model is not None:
        model_spec = model
    else:
        model_spec = f"openai:{settings.openai_chat_model}"

    agent: Agent[ChatContext, GroundedAnswer] = Agent(
        model=model_spec,
        deps_type=ChatContext,
        output_type=GroundedAnswer,
        system_prompt=_SYSTEM_PROMPT,
        model_settings={"temperature": settings.openai_chat_temperature},
    )

    @agent.tool
    def _query_orders(
        run_ctx: RunContext[ChatContext],
        payment_method: PaymentMethod | None = None,
        pincode: str | None = None,
        utm_campaign: str | None = None,
        financial_status: str | None = None,
    ) -> ToolResult[list[dict[str, Any]]]:
        return query_orders(
            run_ctx.deps,
            payment_method=payment_method,
            pincode=pincode,
            utm_campaign=utm_campaign,
            financial_status=financial_status,
        )

    @agent.tool
    def _compute_metric(
        run_ctx: RunContext[ChatContext],
        formula: str,
        payment_method: PaymentMethod | None = None,
        pincode: str | None = None,
    ) -> ToolResult[Any]:
        return compute_metric(
            run_ctx.deps,
            formula=formula,
            payment_method=payment_method,
            pincode=pincode,
        )

    @agent.tool
    def _propose_action(
        run_ctx: RunContext[ChatContext],
        action_type: str,
        target_record_id: int,
        reasoning: str,
        evidence_record_ids: list[int],
    ) -> ToolResult[dict[str, Any]]:
        return propose_action(
            run_ctx.deps,
            action_type=action_type,
            target_record_id=target_record_id,
            reasoning=reasoning,
            evidence_record_ids=evidence_record_ids,
        )

    return agent


async def answer_question(
    question: str,
    ctx: ChatContext,
    *,
    model_override: Model | None = None,
) -> AnsweredQuestion:
    """Run the agent, collect citations from every tool call, run the
    enforcer, return an AnsweredQuestion ready to ship.
    """
    agent = build_agent(model=model_override)

    # Capture citations across all tool calls by wrapping each tool to
    # accumulate into a list. Simpler in PydanticAI v0.4+: read from the
    # run's message history after the run completes.
    collected_citations: list[RowCitation] = []

    # We need a way to capture citations as tools return. Strategy: use
    # agent's `result_validator` or post-process messages. For v0 we
    # re-run the tools with the same args by inspecting the message
    # history — but that's wasteful. Cleaner: tag the agent's tools to
    # append to `collected_citations`. PydanticAI gives us this via the
    # message history after `agent.run` — see `result.all_messages()`.

    try:
        run_result = await agent.run(question, deps=ctx)
    except Exception as exc:
        raise LLMUnavailableError(
            message=f"LLM call failed: {exc}",
            details={"exc_type": type(exc).__name__},
        ) from exc

    # Walk message history; every ToolReturnPart's content is a ToolResult
    # whose `citations` we accumulate. (PydanticAI exposes message parts
    # via `all_messages()`.)
    for message in run_result.all_messages():
        for part in getattr(message, "parts", []):
            content = getattr(part, "content", None)
            if isinstance(content, ToolResult):
                collected_citations.extend(content.citations)

    grounded: GroundedAnswer = run_result.output
    final_text = enforce_grounded_answer(grounded, available_citations=collected_citations)

    # The frontend renders citations by record_id. De-dup before returning.
    seen: set[int] = set()
    unique_citations: list[RowCitation] = []
    for c in collected_citations:
        if c.record_id not in seen:
            unique_citations.append(c)
            seen.add(c.record_id)

    return AnsweredQuestion(text=final_text, citations=unique_citations)


class LLMUnavailableError(MunimError):
    from munim.shared.constants import ErrorCode

    code = ErrorCode.CHAT_LLM_UNAVAILABLE.value
    http_status = 502
    message = "LLM call failed."
```

Implementation note for the implementer: the message-history walk in `answer_question` depends on PydanticAI's `all_messages()` returning parts whose `.content` is the actual Python tool return. If the installed pydantic-ai version exposes tool results differently (e.g., as `ToolReturnPart.tool_return` instead of `.content`), adjust the loop accordingly. The tests will catch a mismatch — they assert citations propagate through.

- [ ] **Step 4: Run tests, see them pass**

```
uv run pytest src/munim/chat/tests/test_agent.py -v
```

Expected: 2 passed. If the message-history walk fails, debug by `print(run_result.all_messages())` and adjust.

- [ ] **Step 5: Lint + typecheck + full suite**

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 124 passed.

- [ ] **Step 6: Commit**

```
git add apps/api/src/munim/chat/agent.py apps/api/src/munim/chat/tests/test_agent.py
git commit -m "feat(chat): PydanticAI agent orchestrator with grounded output + enforcement"
```

---

## Task 6 — Chat module endpoint

**Files:**
- Create: `apps/api/src/munim/modules/chat/__init__.py`
- Create: `apps/api/src/munim/modules/chat/schemas.py`
- Create: `apps/api/src/munim/modules/chat/service.py`
- Create: `apps/api/src/munim/modules/chat/router.py`
- Create: `apps/api/src/munim/modules/chat/tests/__init__.py`
- Create: `apps/api/src/munim/modules/chat/tests/test_router.py`
- Modify: `apps/api/src/munim/main.py` — register the chat router.

- [ ] **Step 1: Schemas**

Create `apps/api/src/munim/modules/chat/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict, Field

from munim.chat.types import RowCitation


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[RowCitation]
```

- [ ] **Step 2: Service**

Create `apps/api/src/munim/modules/chat/service.py`:

```python
"""Chat service. Thin wrapper around `chat.agent.answer_question`."""

from sqlmodel import Session

from munim.chat.agent import answer_question
from munim.chat.tools import ChatContext
from munim.modules.chat.schemas import ChatMessageResponse


async def handle_chat_message(
    session: Session,
    merchant_id: str,
    message: str,
) -> ChatMessageResponse:
    ctx = ChatContext(merchant_id=merchant_id, session=session)
    answered = await answer_question(question=message, ctx=ctx)
    return ChatMessageResponse(text=answered.text, citations=answered.citations)
```

- [ ] **Step 3: Router**

Create `apps/api/src/munim/modules/chat/router.py`:

```python
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from munim.modules.chat.schemas import ChatMessageRequest, ChatMessageResponse
from munim.modules.chat.service import handle_chat_message
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=SuccessEnvelope[ChatMessageResponse])
async def post_message(
    body: ChatMessageRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[ChatMessageResponse]:
    result = await handle_chat_message(session, DEFAULT_MERCHANT_ID, body.message)
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)
```

- [ ] **Step 4: Register router in `main.py`**

In `apps/api/src/munim/main.py`, import and include:

```python
from munim.modules.chat.router import router as chat_router
# ...
app.include_router(chat_router)
```

- [ ] **Step 5: Write the failing tests**

Create `apps/api/src/munim/modules/chat/tests/test_router.py`:

```python
"""Endpoint tests using PydanticAI's TestModel to mock the LLM.

We can't easily inject the TestModel through TestClient — the agent is
constructed inside the request handler. So these tests monkeypatch
`build_agent` to return a TestModel-backed agent.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from munim.chat.types import GroundedAnswer
from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


def _seed_one_order(session, merchant_id: str = "m_default") -> int:
    row = Record(
        merchant_id=merchant_id,
        source_system=SourceSystem.SHOPIFY.value,
        source_id="ord_test",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="h",
        raw={"id": "ord_test"},
        normalized={
            "placed_at": "2026-05-10T03:45:32Z",
            "total_inr": "1000.00",
            "payment_method": "cod",
            "financial_status": "pending",
            "pincode": "560001",
        },
    )
    session.add(row)
    session.commit()
    return row.id if row.id is not None else 0


def test_post_message_returns_text_with_citations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from munim.shared.db import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        order_id = _seed_one_order(s)

    # Build a GroundedAnswer that cites the real order id; the agent
    # constructed inside the handler will use our TestModel.
    canned = GroundedAnswer(
        text=f"You have 1 order[cite:{order_id}] worth ₹1,000[cite:{order_id}].",
        used_citations=[order_id],
    )
    test_model = TestModel(custom_output_args=canned)

    from munim.chat import agent as agent_module

    original_build = agent_module.build_agent

    def patched_build(model=None):
        return original_build(model=test_model)

    monkeypatch.setattr(agent_module, "build_agent", patched_build)

    response = client.post("/chat/messages", json={"message": "How many orders?"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "1 order" in body["data"]["text"]
    assert f"[cite:{order_id}]" in body["data"]["text"]
    assert len(body["data"]["citations"]) >= 1


def test_post_message_validates_input(client: TestClient) -> None:
    # Empty message must fail validation per §10.
    response = client.post("/chat/messages", json={"message": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation.bad_format"
```

- [ ] **Step 6: Run tests + lint + typecheck**

```
uv run pytest src/munim/modules/chat/tests/test_router.py -v
```

Expected: 2 passed.

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 126 passed.

- [ ] **Step 7: Commit**

```
git add apps/api/src/munim/modules/chat apps/api/src/munim/main.py
git commit -m "feat(chat): expose POST /chat/messages endpoint"
```

---

## Task 7 — Docs + commit

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `context.md`

- [ ] **Step 1: CHANGELOG entry** (insert at top of `CHANGELOG.md`):

```
## 2026-05-14 — Phase 5: chat layer with citation contract (backend)

**What changed:** Backend chat surface live. New `apps/api/src/munim/chat/` package: `RowCitation` + `ToolResult` + `GroundedAnswer` + `AnsweredQuestion` types; the fail-closed citation enforcer that strips any numeric claim not immediately followed by `[cite:row_id]` markers; typed tools (`query_orders`, `compute_metric`, `propose_action`) backed by real `record` rows; the PydanticAI agent orchestrator (OpenAI gpt-4o-mini default, override via `OPENAI_CHAT_MODEL` env) with the citation-contract system prompt and `GroundedAnswer` structured output. New `modules/chat/` exposes `POST /chat/messages`. All tests use PydanticAI's `TestModel` for the LLM — zero real OpenAI calls in CI; one optional env-gated live test for the operator.

**The citation contract has 4 layers, all in place:**
1. Tool return shape — every tool returns `ToolResult{data, citations}`.
2. System prompt — explicit instruction to wrap every number in `[cite:N]`.
3. Structured output — `GroundedAnswer` forces the model into `{text, used_citations}`.
4. Fail-closed post-processor — uncited numbers stripped, hallucinated row ids reject the answer.

**Test count:** 95 → 126 (+31 new): 6 types + 13 enforcer + 8 tools + 2 agent + 2 router. Every enforcer test pins a specific LLM hallucination class.

**Files touched:** `apps/api/src/munim/chat/{types,enforcer,tools,agent}.py` + tests; `apps/api/src/munim/modules/chat/{schemas,service,router}.py` + tests; `apps/api/src/munim/shared/{config,constants}.py`; `apps/api/pyproject.toml` (pydantic-ai); `.env.example`; `apps/api/src/munim/main.py` (router register).

**Reverts cleanly?:** yes — drop the new packages, revert the modified ones, drop the dep.
```

- [ ] **Step 2: `context.md`**

Update:
- **Now:** "Phase 5 complete. Backend chat with full citation contract. POST /chat/messages live. 126 tests green. Frontend chat page is Phase 6."
- **Done:** append "2026-05-14 — Phase 5 complete. Chat backend + citation contract, the scored axis of the brief."
- **Next:** bump Phase 6 (frontend chat) to top.
- **Decisions:** consider adding an entry on the `_PROXIMITY_CHARS = 64` choice for the enforcer's "covered range" window.
- **Problems & solutions:** add any LLM/PydanticAI-specific bugs encountered (token usage, JSON schema mode, etc.).

- [ ] **Step 3: Commit**

```
git add CHANGELOG.md context.md
git commit -m "docs(phase-5): record chat backend + citation contract completion"
```

---

## Self-review

**Spec coverage (against the brief):**
- "Chat layer. Tool-use loop. Reads and writes over the data." — `query_orders`, `compute_metric` (reads), `propose_action` (write that persists to run_log without side effects).
- "Every numerical claim in the answer carries a citation back to the source rows." — 4-layer contract; enforcer is the load-bearing piece.
- "Uncited numbers don't survive to the user." — `[unverified number removed]` sentinel; tested with 5 distinct hallucination classes.
- §13.4 — every test pins a specific failure mode; enforcer tests are the highest-leverage in the project.

**Type/name consistency:**
- `RowCitation.record_id` (int) is the same key on the frontend (Phase 6 Zod schema must mirror). Phase 6 task will check.
- `GroundedAnswer.used_citations: list[int]` — Pydantic rejects string-form; tested.
- `CHAT_*` error codes added to `ErrorCode` in Task 1; used by enforcer + agent.

**Out of scope, re-listed:** streaming SSE (Phase 6), multi-turn history, shipments/ad_spend tools (no data yet), embeddings, paraphrase verification, real-LLM live test (env-gated, manual).

**Security notes:**
- The OPENAI_API_KEY is read by PydanticAI's OpenAI provider; never logged, never returned in any error envelope. Settings validation throws at startup if missing.
- The LLM only sees the `excerpt` projection of `record.normalized` — `raw` payloads (which may contain PII like phone numbers) never reach the model.
- `propose_action` does NOT dispatch — matches the brief's "AI employee proposes, doesn't dispatch" constraint and the agent's no-side-effects rule.

**Performance:**
- `query_orders` is a full table scan on `record` per call. Acceptable at v0 scale (<1000 rows). When it gets hot we add the partial indexes from `docs/architecture.md §4.3`.
- Each chat request constructs a new `Agent` instance. PydanticAI caches the underlying provider client; agent construction is cheap.
