from munim.agents.daily_briefing.schemas import BriefingOutput, ProposedAction


def test_briefing_output_roundtrip() -> None:
    out = BriefingOutput(
        narrative="You had 3 orders[cite:1,2,3] worth Rs.12,000[cite:1,2,3].",
        proposed_actions=[
            ProposedAction(
                action_type="Convert COD order to prepaid",
                reasoning="Customer #C001 has returned 3 of 5 prior shipments[cite:5].",
                evidence_record_ids=[5],
            )
        ],
        used_citations=[1, 2, 3, 5],
    )
    payload = out.model_dump()
    assert payload["narrative"].startswith("You had 3 orders")
    assert payload["proposed_actions"][0]["evidence_record_ids"] == [5]


def test_briefing_output_empty_actions_allowed() -> None:
    out = BriefingOutput(
        narrative="Quiet week — only Rs.500[cite:1] in spend.",
        used_citations=[1],
    )
    assert out.proposed_actions == []
