from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from munim.agents.rto_mitigator.signals import SignalResult
from munim.shared.constants import AgentActionType

_CONVERT_THRESHOLD = 0.6
_CALL_THRESHOLD = 0.4
_CONVERT_SUCCESS_RATE = 0.7
_CALL_SUCCESS_RATE = 0.4


class RTOWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = 0.25
    pincode: float = 0.30
    time: float = 0.15
    customer: float = 0.20
    category: float = 0.10


@dataclass
class RTODecision:
    score: float
    action: AgentActionType
    estimated_inr_saved: Decimal
    signal_scores: dict[str, float]
    signal_diagnostics: dict[str, dict[str, Any]]
    weights: RTOWeights
    reasoning: str = ""


def score_signals(
    signals: dict[str, SignalResult],
    *,
    total_inr: Decimal,
    weights: RTOWeights | None = None,
) -> RTODecision:
    w = weights if weights is not None else RTOWeights()

    weight_map = {
        "value": w.value,
        "pincode": w.pincode,
        "time": w.time,
        "customer": w.customer,
        "category": w.category,
    }
    score = 0.0
    for name, signal in signals.items():
        score += signal.score * weight_map.get(name, 0.0)
    score = min(score, 1.0)

    if score >= _CONVERT_THRESHOLD:
        action = AgentActionType.CONVERT_TO_PREPAID
        success_rate = _CONVERT_SUCCESS_RATE
    elif score >= _CALL_THRESHOLD:
        action = AgentActionType.CONFIRMATION_CALL
        success_rate = _CALL_SUCCESS_RATE
    else:
        action = AgentActionType.NO_ACTION
        success_rate = 0.0

    estimated_saved = (total_inr * Decimal(str(score)) * Decimal(str(success_rate))).quantize(
        Decimal("0.01")
    )

    reasoning = _build_reasoning(score, action, signals)
    return RTODecision(
        score=score,
        action=action,
        estimated_inr_saved=(
            estimated_saved if action is not AgentActionType.NO_ACTION else Decimal("0")
        ),
        signal_scores={name: s.score for name, s in signals.items()},
        signal_diagnostics={name: s.diagnostic for name, s in signals.items()},
        weights=w,
        reasoning=reasoning,
    )


def _build_reasoning(
    score: float, action: AgentActionType, signals: dict[str, SignalResult]
) -> str:
    top_signal = max(signals.items(), key=lambda kv: kv[1].score)
    return (
        f"score={score:.2f} -> {action.value}; "
        f"top signal: {top_signal[0]}={top_signal[1].score:.2f} "
        f"({top_signal[1].diagnostic})"
    )
