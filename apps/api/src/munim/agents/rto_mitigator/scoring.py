from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from munim.agents.rto_mitigator.signals import SignalResult
from munim.shared.constants import AgentActionType

_CONVERT_THRESHOLD = Decimal("0.6")
_CALL_THRESHOLD = Decimal("0.4")
_CONVERT_SUCCESS_RATE = Decimal("0.7")
_CALL_SUCCESS_RATE = Decimal("0.4")
_NO_ACTION_SUCCESS_RATE = Decimal("0")


class RTOWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = 0.28
    pincode: float = 0.33
    time: float = 0.17
    customer: float = 0.22


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

    weight_map: dict[str, Decimal] = {
        "value": Decimal(str(w.value)),
        "pincode": Decimal(str(w.pincode)),
        "time": Decimal(str(w.time)),
        "customer": Decimal(str(w.customer)),
    }
    score = Decimal("0")
    for name, signal in signals.items():
        wt = weight_map.get(name)
        if wt is None:
            continue
        score += Decimal(str(signal.score)) * wt
    if score > Decimal("1"):
        score = Decimal("1")

    if score >= _CONVERT_THRESHOLD:
        action = AgentActionType.CONVERT_TO_PREPAID
        success_rate = _CONVERT_SUCCESS_RATE
    elif score >= _CALL_THRESHOLD:
        action = AgentActionType.CONFIRMATION_CALL
        success_rate = _CALL_SUCCESS_RATE
    else:
        action = AgentActionType.NO_ACTION
        success_rate = _NO_ACTION_SUCCESS_RATE

    estimated_saved = (total_inr * score * success_rate).quantize(Decimal("0.01"))
    if action is AgentActionType.NO_ACTION:
        estimated_saved = Decimal("0")

    reasoning = _build_reasoning(score, action, signals)
    return RTODecision(
        score=float(score),
        action=action,
        estimated_inr_saved=estimated_saved,
        signal_scores={name: s.score for name, s in signals.items()},
        signal_diagnostics={name: s.diagnostic for name, s in signals.items()},
        weights=w,
        reasoning=reasoning,
    )


def _build_reasoning(
    score: Decimal, action: AgentActionType, signals: dict[str, SignalResult]
) -> str:
    top_signal = max(signals.items(), key=lambda kv: kv[1].score)
    return (
        f"score={float(score):.2f} -> {action.value}; "
        f"top signal: {top_signal[0]}={top_signal[1].score:.2f} "
        f"({top_signal[1].diagnostic})"
    )
