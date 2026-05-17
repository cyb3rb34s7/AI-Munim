"""Structured output for the daily-briefing LLM agent.

`BriefingOutput.narrative` carries inline `[cite:N,...]` markers — the
same contract as `chat.types.GroundedAnswer.text`. The existing
`chat.enforcer.enforce_grounded_answer` post-processor consumes it.

`proposed_actions` is a separate list (1-3 items). Each action has its
own short reasoning string; the reasoning ALSO follows the citation
contract so the operator can hover and see the source row.
"""

from pydantic import BaseModel, ConfigDict, Field


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str = Field(
        description="Plain-English action title, e.g. 'Convert COD order to prepaid'."
    )
    reasoning: str = Field(
        description=(
            "1-2 sentences explaining why. Every numeric claim must carry a "
            "[cite:row_id] marker referencing a row from the tools."
        )
    )
    evidence_record_ids: list[int] = Field(
        default_factory=list,
        description="Row ids that justify this action.",
    )


class BriefingOutput(BaseModel):
    # NOTE: extra="forbid" omitted by design — PydanticAI's structured-output
    # JSON schema serialisation can inject bookkeeping fields. Same exception
    # as `chat.types.GroundedAnswer`.

    narrative: str = Field(
        description=(
            "4-6 sentences covering what happened over the last 7 days. "
            "Every numeric claim carries an inline [cite:row_id] marker."
        )
    )
    proposed_actions: list[ProposedAction] = Field(
        default_factory=list,
        description="1-3 concrete actions. May be empty if nothing needs intervention.",
    )
    used_citations: list[int] = Field(
        default_factory=list,
        description="Union of every row_id cited in narrative or proposed_actions.",
    )
