from decimal import Decimal

from munim.agents.rto_mitigator.scoring import (
    RTODecision,
    RTOWeights,
    score_signals,
)
from munim.agents.rto_mitigator.signals import SignalResult
from munim.shared.constants import AgentActionType


def _signals(
    value: float = 0.5,
    pincode: float = 0.2,
    time: float = 0.2,
    customer: float = 0.2,
) -> dict[str, SignalResult]:
    return {
        "value": SignalResult(score=value, diagnostic={}),
        "pincode": SignalResult(score=pincode, diagnostic={}),
        "time": SignalResult(score=time, diagnostic={}),
        "customer": SignalResult(score=customer, diagnostic={}),
    }


def test_low_score_returns_no_action() -> None:
    signals = _signals(value=0.2, pincode=0.2, time=0.2, customer=0.2)
    decision = score_signals(signals, total_inr=Decimal("1000"))
    assert decision.action is AgentActionType.NO_ACTION
    assert decision.score < 0.4
    assert decision.estimated_inr_saved == Decimal("0")


def test_mid_score_returns_confirmation_call() -> None:
    signals = _signals(value=0.5, pincode=0.5, time=0.4, customer=0.4)
    decision = score_signals(signals, total_inr=Decimal("2000"))
    assert decision.action is AgentActionType.CONFIRMATION_CALL
    assert 0.4 <= decision.score < 0.6


def test_high_score_returns_convert_to_prepaid() -> None:
    signals = _signals(value=0.8, pincode=0.7, time=0.7, customer=0.6)
    decision = score_signals(signals, total_inr=Decimal("5000"))
    assert decision.action is AgentActionType.CONVERT_TO_PREPAID
    assert decision.score >= 0.6


def test_estimated_inr_saved_is_proportional_to_order_value() -> None:
    signals = _signals(value=0.8, pincode=0.7, time=0.7, customer=0.6)
    low = score_signals(signals, total_inr=Decimal("1000"))
    high = score_signals(signals, total_inr=Decimal("10000"))
    assert high.estimated_inr_saved > low.estimated_inr_saved


def test_decision_records_all_signal_scores_in_diagnostic() -> None:
    signals = _signals()
    decision = score_signals(signals, total_inr=Decimal("1000"))
    assert "value" in decision.signal_scores
    assert "pincode" in decision.signal_scores
    assert "time" in decision.signal_scores
    assert "customer" in decision.signal_scores
    assert isinstance(decision, RTODecision)


def test_weights_default_sum_to_one() -> None:
    w = RTOWeights()
    total = w.value + w.pincode + w.time + w.customer + w.category
    assert abs(total - 1.0) < 1e-9
