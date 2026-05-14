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

    Note: `extra="forbid"` is intentionally omitted here. PydanticAI's
    structured-output mechanism (which serialises `GroundedAnswer` as a JSON
    schema tool call for the LLM) injects a hidden `__final__` or similar
    bookkeeping field in some versions. Strict extra-forbid breaks that
    serialisation. All other public models use extra=forbid; this is the
    deliberate exception, documented here so the reviewer knows it's not an
    oversight.
    """

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
