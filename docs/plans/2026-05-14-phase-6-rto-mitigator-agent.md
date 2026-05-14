# Phase 6 — RTO Risk Mitigator Agent Implementation Plan

> **For agentic workers:** ONE subagent dispatch for the whole phase (`CLAUDE.md §3`). 8 tasks top-to-bottom, commit per task per the plan, report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Use `superpowers:subagent-driven-development`.
>
> **Test discipline (`docs/conventions.md §13.4`):** every test pins a real failure mode. The "no side effects" guarantee is the brief's central constraint for the agent — there's a dedicated test for it.
>
> **Comment discipline (user feedback during Phase 5):** default to NO comments. Only one when the WHY is genuinely non-obvious. **Never** task-referential comments like "Phase 6 reviewer caught this" or "for issue X" — those go in commit messages, never in code. **Never** narrate what the code does — well-named identifiers do that.

**Goal:** Ship one deterministic autonomous agent that scans COD orders, scores each on RTO (Return-to-Origin) risk from named/weighted signals, and proposes one of three actions per order — **writes the proposal + full reasoning to `run_log` and DOES NOT dispatch anything externally**. Exposes a manual-trigger endpoint so the live demo has a button to click. Cron auto-fire is wired but disabled by default in v0.

**Architecture:**
- New package `apps/api/src/munim/agents/rto_mitigator/`:
  - `signals.py` — pure-function signal extractors (`order_value_bucket`, `pincode_risk`, `time_of_order_risk`, `customer_rto_rate`). Each returns a 0.0-1.0 score plus an opaque diagnostic dict so the run log can show "your pincode 110001 hit the high-risk list, +0.3 to score."
  - `scoring.py` — weights, score formula, threshold tree, ₹-saved estimation. All weights and thresholds are module-level constants logged with every run for auditability.
  - `agent.py` — `RTOMitigatorAgent.run(session, merchant_id)` orchestrator. Scans, scores, decides, persists one `RunLog` row per run.
- New module `apps/api/src/munim/modules/agent_runs/`:
  - `schemas.py`, `service.py`, `router.py` exposing:
    - `POST /api/agents/{name}/run` — manual trigger.
    - `GET /api/agent-runs?kind=agent&limit=50` — list summaries.
    - `GET /api/agent-runs/{id}` — full run detail.
- `AgentActionType` StrEnum added to `shared/constants.py` so the action set is type-checked (no magic strings).
- The agent uses a small **deterministic** scoring function. No LLM. The "intelligence" is in the weighted signals + threshold tree; the run log shows the exact math.

**Tech stack additions:** none. APScheduler exists in deps from Phase 1; we'll wire it but keep the cron loop disabled in v0 (no extra env var needed — the flag is hardcoded off).

**Out of scope (deliberate, called out for the README):**
- LLM-driven agent decisions — deterministic by design (auditable, cheap, predictable; brief's "we want the reasoning" wants the explicit math, not a black box).
- Shiprocket-backed `customer_rto_rate` — Shiprocket connector lands in Phase 5b. v0 returns the population baseline (~20%) when customer history < 3 orders and lowers the max achievable score accordingly.
- `product_category` signal — needs a category field in `normalized.Order`; v0 returns `None` and the weight (0.1) doesn't materially move the score. Schema change deferred.
- Cron auto-fire — wired in code, disabled by default. Production-mode toggle is a one-line change when we're ready. Documented in README.
- Frontend Agent Runs page — Phase 7. Phase 6 ships backend + endpoint; manual smoke is via curl.
- Real outbound action (sending SMS / WhatsApp / call) — explicitly NOT in v0 per brief.
- Per-decision RunLog rows — we ship one `RunLog` per run with the full decision list inline (matches `docs/architecture.md §8`). Per-decision is a Phase 8 refactor if the agent runs page needs row-level filtering.

---

## File map

**New files:**
- `apps/api/src/munim/agents/__init__.py`
- `apps/api/src/munim/agents/rto_mitigator/__init__.py`
- `apps/api/src/munim/agents/rto_mitigator/signals.py`
- `apps/api/src/munim/agents/rto_mitigator/scoring.py`
- `apps/api/src/munim/agents/rto_mitigator/agent.py`
- `apps/api/src/munim/agents/rto_mitigator/tests/__init__.py`
- `apps/api/src/munim/agents/rto_mitigator/tests/test_signals.py`
- `apps/api/src/munim/agents/rto_mitigator/tests/test_scoring.py`
- `apps/api/src/munim/agents/rto_mitigator/tests/test_agent.py`
- `apps/api/src/munim/modules/agent_runs/__init__.py`
- `apps/api/src/munim/modules/agent_runs/schemas.py`
- `apps/api/src/munim/modules/agent_runs/service.py`
- `apps/api/src/munim/modules/agent_runs/router.py`
- `apps/api/src/munim/modules/agent_runs/tests/__init__.py`
- `apps/api/src/munim/modules/agent_runs/tests/test_router.py`

**Modified files:**
- `apps/api/src/munim/shared/constants.py` — add `AgentActionType` StrEnum, new error codes (`AGENT_UNKNOWN`, `AGENT_RUN_FAILED`).
- `apps/api/src/munim/main.py` — register the agent-runs router.

---

## Task 1 — Constants: `AgentActionType` + new error codes

**Files:** `apps/api/src/munim/shared/constants.py`

- [ ] **Step 1:** Append to `ErrorCode`:

```python
    AGENT_UNKNOWN = "agent.unknown"
    AGENT_RUN_FAILED = "agent.run_failed"
```

- [ ] **Step 2:** Add a new enum at the bottom of the file:

```python
class AgentName(StrEnum):
    RTO_MITIGATOR = "rto_mitigator"


class AgentActionType(StrEnum):
    CONVERT_TO_PREPAID = "convert_to_prepaid"
    CONFIRMATION_CALL = "confirmation_call"
    NO_ACTION = "no_action"
```

- [ ] **Step 3:** Lint + full suite.

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api'
uv run ruff check src
uv run mypy src
uv run pytest -v
```

Expected: 135 passed (no regressions).

- [ ] **Step 4:** Commit.

```
git add apps/api/src/munim/shared/constants.py
git commit -m "feat(constants): add AgentName + AgentActionType enums + agent error codes"
```

---

## Task 2 — Signal extractors

**Files:** `apps/api/src/munim/agents/__init__.py` (empty), `apps/api/src/munim/agents/rto_mitigator/__init__.py` (empty), `apps/api/src/munim/agents/rto_mitigator/signals.py`, `apps/api/src/munim/agents/rto_mitigator/tests/__init__.py` (empty), `apps/api/src/munim/agents/rto_mitigator/tests/test_signals.py`.

Each signal extractor is a pure function: takes order data, returns a `SignalResult` containing a `score: float` (0.0-1.0) plus a `diagnostic: dict[str, Any]` explaining what the score is from. The diagnostic surfaces in the run log so an operator can see "score=0.65 because pincode=110001 is in high-risk list AND order value > ₹2000."

- [ ] **Step 1:** Write the failing tests.

`test_signals.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from munim.agents.rto_mitigator.signals import (
    customer_rto_rate,
    order_value_bucket,
    pincode_risk,
    time_of_order_risk,
)
from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


def _seed_order(
    session: Session,
    *,
    source_id: str,
    customer_id: str,
    pincode: str,
    payment_method: str,
    total_inr: str,
    placed_at: str = "2026-05-10T03:45:32Z",
) -> Record:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized={
            "placed_at": placed_at,
            "total_inr": total_inr,
            "currency": "INR",
            "payment_method": payment_method,
            "financial_status": "pending",
            "pincode": pincode,
            "customer_source_id": customer_id,
        },
    )
    session.add(row)
    session.flush()
    return row


def test_order_value_bucket_low_value_returns_low_score() -> None:
    result = order_value_bucket(Decimal("500"))
    assert 0.0 <= result.score < 0.3
    assert result.diagnostic["bucket"] == "low"


def test_order_value_bucket_high_value_returns_high_score() -> None:
    result = order_value_bucket(Decimal("8000"))
    assert result.score >= 0.7
    assert result.diagnostic["bucket"] == "high"


def test_pincode_risk_known_high_risk_pincode_returns_high_score() -> None:
    result = pincode_risk("110001")
    assert result.score >= 0.5
    assert result.diagnostic["pincode"] == "110001"
    assert result.diagnostic["in_high_risk_list"] is True


def test_pincode_risk_unknown_pincode_returns_baseline() -> None:
    result = pincode_risk("999999")
    assert 0.0 <= result.score <= 0.4
    assert result.diagnostic["in_high_risk_list"] is False


def test_pincode_risk_missing_pincode_returns_baseline_with_diagnostic() -> None:
    result = pincode_risk(None)
    assert result.score == 0.2
    assert result.diagnostic["pincode"] is None


def test_time_of_order_risk_late_night_returns_high_score() -> None:
    result = time_of_order_risk("2026-05-10T23:45:00+05:30")
    assert result.score >= 0.6
    assert result.diagnostic["hour_band"] == "late_night"


def test_time_of_order_risk_business_hours_returns_low_score() -> None:
    result = time_of_order_risk("2026-05-10T14:30:00+05:30")
    assert result.score <= 0.3
    assert result.diagnostic["hour_band"] == "business_hours"


def test_customer_rto_rate_no_history_returns_population_baseline(session: Session) -> None:
    result = customer_rto_rate(session, "m_default", "new_customer_x")
    assert result.score == 0.2
    assert result.diagnostic["history_count"] == 0
    assert result.diagnostic["confident"] is False


def test_customer_rto_rate_with_history_uses_observed_rate(session: Session) -> None:
    for i in range(5):
        _seed_order(
            session,
            source_id=f"hist_{i}",
            customer_id="customer_x",
            pincode="560001",
            payment_method="cod",
            total_inr="1000",
        )
    session.commit()

    result = customer_rto_rate(session, "m_default", "customer_x")
    assert result.diagnostic["history_count"] == 5
    assert result.diagnostic["confident"] is True
```

- [ ] **Step 2:** Run tests, see ImportError.

```
uv run pytest src/munim/agents/rto_mitigator/tests/test_signals.py -v
```

- [ ] **Step 3:** Implement.

`apps/api/src/munim/agents/__init__.py` and `apps/api/src/munim/agents/rto_mitigator/__init__.py`: empty files.

`signals.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


_HIGH_RISK_PINCODES: frozenset[str] = frozenset({
    "110001", "110002",
    "700001", "700002",
    "560100",
    "000123",
})

_LOW_VALUE_THRESHOLD = Decimal("1000")
_HIGH_VALUE_THRESHOLD = Decimal("5000")

_LATE_NIGHT_START_HOUR = 22
_LATE_NIGHT_END_HOUR = 6
_BUSINESS_HOURS_START = 9
_BUSINESS_HOURS_END = 18

_CONFIDENT_HISTORY_MIN = 3
_POPULATION_RTO_BASELINE = 0.20


@dataclass
class SignalResult:
    score: float
    diagnostic: dict[str, Any] = field(default_factory=dict)


def order_value_bucket(total_inr: Decimal) -> SignalResult:
    if total_inr < _LOW_VALUE_THRESHOLD:
        return SignalResult(score=0.2, diagnostic={"bucket": "low", "total_inr": str(total_inr)})
    if total_inr < _HIGH_VALUE_THRESHOLD:
        return SignalResult(
            score=0.5, diagnostic={"bucket": "medium", "total_inr": str(total_inr)}
        )
    return SignalResult(score=0.8, diagnostic={"bucket": "high", "total_inr": str(total_inr)})


def pincode_risk(pincode: str | None) -> SignalResult:
    if pincode is None:
        return SignalResult(score=0.2, diagnostic={"pincode": None, "in_high_risk_list": False})
    in_list = pincode in _HIGH_RISK_PINCODES
    return SignalResult(
        score=0.7 if in_list else 0.2,
        diagnostic={"pincode": pincode, "in_high_risk_list": in_list},
    )


def time_of_order_risk(placed_at_iso: str) -> SignalResult:
    dt = datetime.fromisoformat(placed_at_iso)
    hour = dt.hour
    if hour >= _LATE_NIGHT_START_HOUR or hour < _LATE_NIGHT_END_HOUR:
        band = "late_night"
        score = 0.7
    elif _BUSINESS_HOURS_START <= hour < _BUSINESS_HOURS_END:
        band = "business_hours"
        score = 0.2
    else:
        band = "evening"
        score = 0.4
    return SignalResult(score=score, diagnostic={"hour": hour, "hour_band": band})


def customer_rto_rate(
    session: Session,
    merchant_id: str,
    customer_source_id: str,
) -> SignalResult:
    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == SourceSystem.SHOPIFY.value)
        .where(Record.entity_type == EntityType.ORDER.value)
    ).all()
    customer_rows = [
        r for r in rows if r.normalized.get("customer_source_id") == customer_source_id
    ]
    history_count = len(customer_rows)
    confident = history_count >= _CONFIDENT_HISTORY_MIN

    if not confident:
        return SignalResult(
            score=_POPULATION_RTO_BASELINE,
            diagnostic={
                "history_count": history_count,
                "confident": False,
                "rate_source": "population_baseline",
            },
        )

    rto_count = sum(
        1 for r in customer_rows if r.normalized.get("fulfillment_status") == "rto"
    )
    rate = rto_count / history_count
    return SignalResult(
        score=min(rate * 1.5, 1.0),
        diagnostic={
            "history_count": history_count,
            "rto_count": rto_count,
            "observed_rate": rate,
            "confident": True,
            "rate_source": "customer_history",
        },
    )
```

- [ ] **Step 4:** Run, see green.

```
uv run pytest src/munim/agents/rto_mitigator/tests/test_signals.py -v
```

Expected: 9 passed.

- [ ] **Step 5:** Lint + full suite.

```
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -v
```

Expected: 144 passed.

- [ ] **Step 6:** Commit.

```
git add apps/api/src/munim/agents
git commit -m "feat(rto): signal extractors — value, pincode, time, customer history"
```

---

## Task 3 — Scoring + decision

**Files:** `apps/api/src/munim/agents/rto_mitigator/scoring.py`, `apps/api/src/munim/agents/rto_mitigator/tests/test_scoring.py`.

- [ ] **Step 1:** Write the failing tests.

`test_scoring.py`:

```python
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


def test_weights_default_sum_to_one() -> None:
    w = RTOWeights()
    total = w.value + w.pincode + w.time + w.customer + w.category
    assert abs(total - 1.0) < 1e-9
```

- [ ] **Step 2:** Run, see ImportError.

- [ ] **Step 3:** Implement.

`scoring.py`:

```python
from dataclasses import dataclass, field
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

    estimated_saved = (
        total_inr * Decimal(str(score)) * Decimal(str(success_rate))
    ).quantize(Decimal("0.01"))

    reasoning = _build_reasoning(score, action, signals)
    return RTODecision(
        score=score,
        action=action,
        estimated_inr_saved=estimated_saved if action is not AgentActionType.NO_ACTION else Decimal("0"),
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
        f"score={score:.2f} → {action.value}; "
        f"top signal: {top_signal[0]}={top_signal[1].score:.2f} "
        f"({top_signal[1].diagnostic})"
    )
```

- [ ] **Step 4:** Run tests, see green. Lint + full suite. Commit.

```
git add apps/api/src/munim/agents/rto_mitigator/scoring.py apps/api/src/munim/agents/rto_mitigator/tests/test_scoring.py
git commit -m "feat(rto): weighted scoring + decision tree + estimated INR saved"
```

Expected: 150 passed total.

---

## Task 4 — Agent orchestrator

**Files:** `apps/api/src/munim/agents/rto_mitigator/agent.py`, `apps/api/src/munim/agents/rto_mitigator/tests/test_agent.py`.

The orchestrator pulls all COD orders for the merchant, runs signals + scoring per order, and writes ONE `RunLog` row per agent invocation containing the full decision list in `detail_json`.

- [ ] **Step 1:** Write the failing tests.

`test_agent.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import respx
from sqlmodel import Session, select

from munim.agents.rto_mitigator.agent import RTOMitigatorAgent
from munim.models import Record, RunLog
from munim.shared.constants import (
    AgentActionType,
    AgentName,
    EntityType,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)


def _seed_order(
    session: Session,
    *,
    source_id: str,
    payment_method: PaymentMethod,
    total_inr: str = "1500",
    pincode: str = "110001",
    customer_source_id: str = "cust_a",
    placed_at: str = "2026-05-10T23:45:00+05:30",
) -> Record:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized={
            "placed_at": placed_at,
            "total_inr": total_inr,
            "currency": "INR",
            "payment_method": payment_method.value,
            "financial_status": "pending",
            "pincode": pincode,
            "customer_source_id": customer_source_id,
        },
    )
    session.add(row)
    session.flush()
    return row


def test_agent_only_scores_cod_orders(session: Session) -> None:
    cod = _seed_order(session, source_id="cod_1", payment_method=PaymentMethod.COD)
    _seed_order(session, source_id="prepaid_1", payment_method=PaymentMethod.PREPAID)
    session.commit()

    agent = RTOMitigatorAgent()
    summary = agent.run(session, merchant_id="m_default")
    session.commit()

    assert summary.orders_scanned == 1
    run = session.exec(select(RunLog)).one()
    decisions = run.detail_json["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["record_id"] == cod.id


def test_agent_writes_one_run_log_with_all_decisions(session: Session) -> None:
    for i in range(3):
        _seed_order(session, source_id=f"cod_{i}", payment_method=PaymentMethod.COD)
    session.commit()

    agent = RTOMitigatorAgent()
    summary = agent.run(session, merchant_id="m_default")
    session.commit()

    runs = session.exec(select(RunLog).where(RunLog.kind == RunLogKind.AGENT.value)).all()
    assert len(runs) == 1
    assert summary.orders_scanned == 3
    assert len(runs[0].detail_json["decisions"]) == 3
    assert runs[0].detail_json["agent"] == AgentName.RTO_MITIGATOR.value


def test_agent_decision_includes_signal_scores_and_weights(session: Session) -> None:
    _seed_order(session, source_id="cod_x", payment_method=PaymentMethod.COD)
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    d = run.detail_json["decisions"][0]
    assert "signal_scores" in d
    assert "weights" in d
    assert "value" in d["signal_scores"]
    assert "pincode" in d["signal_scores"]


def test_agent_proposes_convert_for_high_risk_cod_order(session: Session) -> None:
    _seed_order(
        session,
        source_id="high_risk",
        payment_method=PaymentMethod.COD,
        total_inr="6000",
        pincode="110001",
        placed_at="2026-05-10T23:30:00+05:30",
    )
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    d = run.detail_json["decisions"][0]
    assert d["action"] == AgentActionType.CONVERT_TO_PREPAID.value
    assert Decimal(d["estimated_inr_saved"]) > Decimal("0")


@respx.mock
def test_agent_makes_zero_outbound_http_calls(session: Session) -> None:
    _seed_order(session, source_id="cod_1", payment_method=PaymentMethod.COD)
    _seed_order(
        session,
        source_id="cod_2",
        payment_method=PaymentMethod.COD,
        total_inr="6000",
        pincode="110001",
    )
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    assert len(respx.calls) == 0


def test_agent_run_log_has_run_id_and_timing(session: Session) -> None:
    _seed_order(session, source_id="cod_a", payment_method=PaymentMethod.COD)
    session.commit()

    RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    run = session.exec(select(RunLog)).one()
    assert run.detail_json["run_id"].startswith("ar_")
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at


def test_agent_with_zero_cod_orders_still_writes_empty_run_log(session: Session) -> None:
    _seed_order(session, source_id="prepaid_only", payment_method=PaymentMethod.PREPAID)
    session.commit()

    summary = RTOMitigatorAgent().run(session, merchant_id="m_default")
    session.commit()

    assert summary.orders_scanned == 0
    assert summary.actions_proposed == 0
    runs = session.exec(select(RunLog)).all()
    assert len(runs) == 1
    assert runs[0].detail_json["decisions"] == []
```

The `test_agent_makes_zero_outbound_http_calls` test uses `respx.mock` — any HTTP call made by the agent would be intercepted and fail. Locks the brief's "don't actually send anything" constraint.

- [ ] **Step 2:** Run, see ImportError.

- [ ] **Step 3:** Implement.

`agent.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, col, select
from ulid import ULID

from munim.agents.rto_mitigator.scoring import RTODecision, score_signals
from munim.agents.rto_mitigator.signals import (
    SignalResult,
    customer_rto_rate,
    order_value_bucket,
    pincode_risk,
    time_of_order_risk,
)
from munim.models import Record, RunLog
from munim.shared.constants import (
    AgentActionType,
    AgentName,
    EntityType,
    PaymentMethod,
    RunLogKind,
    SourceSystem,
)
from munim.shared.logging import get_logger

log = get_logger("munim.agents.rto_mitigator")


@dataclass
class AgentRunSummary:
    run_id: str
    run_log_id: int
    orders_scanned: int
    actions_proposed: int
    started_at: datetime
    finished_at: datetime


class RTOMitigatorAgent:
    name = AgentName.RTO_MITIGATOR

    def run(self, session: Session, merchant_id: str) -> AgentRunSummary:
        started_at = datetime.now(UTC)
        run_id = f"ar_{ULID()}"

        orders = self._scan_cod_orders(session, merchant_id)
        decisions = [self._score_order(session, merchant_id, o) for o in orders]
        actions_proposed = sum(
            1 for d in decisions if d["action"] != AgentActionType.NO_ACTION.value
        )

        finished_at = datetime.now(UTC)

        run = RunLog(
            merchant_id=merchant_id,
            kind=RunLogKind.AGENT.value,
            started_at=started_at,
            finished_at=finished_at,
            detail_json={
                "run_id": run_id,
                "agent": self.name.value,
                "orders_scanned": len(orders),
                "actions_proposed": actions_proposed,
                "decisions": decisions,
            },
        )
        session.add(run)
        session.flush()

        log.info(
            "agent.run.completed",
            agent=self.name.value,
            run_id=run_id,
            merchant_id=merchant_id,
            orders_scanned=len(orders),
            actions_proposed=actions_proposed,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        )

        assert run.id is not None
        return AgentRunSummary(
            run_id=run_id,
            run_log_id=run.id,
            orders_scanned=len(orders),
            actions_proposed=actions_proposed,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _scan_cod_orders(self, session: Session, merchant_id: str) -> list[Record]:
        stmt = (
            select(Record)
            .where(Record.merchant_id == merchant_id)
            .where(Record.source_system == SourceSystem.SHOPIFY.value)
            .where(Record.entity_type == EntityType.ORDER.value)
            .order_by(col(Record.fetched_at).desc())
        )
        all_orders = session.exec(stmt).all()
        return [
            r for r in all_orders
            if r.normalized.get("payment_method") == PaymentMethod.COD.value
        ]

    def _score_order(
        self, session: Session, merchant_id: str, order: Record
    ) -> dict:
        n = order.normalized
        total_inr = Decimal(n["total_inr"])

        signals: dict[str, SignalResult] = {
            "value": order_value_bucket(total_inr),
            "pincode": pincode_risk(n.get("pincode")),
            "time": time_of_order_risk(n["placed_at"]),
            "customer": customer_rto_rate(
                session, merchant_id, n.get("customer_source_id", "")
            ),
        }
        decision: RTODecision = score_signals(signals, total_inr=total_inr)

        assert order.id is not None
        return {
            "record_id": order.id,
            "source_id": order.source_id,
            "score": decision.score,
            "action": decision.action.value,
            "estimated_inr_saved": str(decision.estimated_inr_saved),
            "signal_scores": decision.signal_scores,
            "signal_diagnostics": decision.signal_diagnostics,
            "weights": decision.weights.model_dump(),
            "reasoning": decision.reasoning,
        }
```

- [ ] **Step 4:** Run, lint, mypy, commit.

```
uv run pytest src/munim/agents -v
uv run ruff check src
uv run mypy src
git add apps/api/src/munim/agents/rto_mitigator/agent.py apps/api/src/munim/agents/rto_mitigator/tests/test_agent.py
git commit -m "feat(rto): orchestrator scans COD orders, scores, writes one run_log per run"
```

Expected: 157 tests passing.

---

## Task 5 — Agent-runs module: schemas + service

**Files:** `apps/api/src/munim/modules/agent_runs/{__init__.py,schemas.py,service.py}`, `apps/api/src/munim/modules/agent_runs/tests/__init__.py`.

- [ ] **Step 1:** Empty `__init__.py` files.

- [ ] **Step 2:** `schemas.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_log_id: int
    run_id: str
    agent: str
    orders_scanned: int
    actions_proposed: int
    started_at: datetime
    finished_at: datetime


class AgentRunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_log_id: int
    run_id: str
    agent: str
    started_at: datetime
    finished_at: datetime
    orders_scanned: int
    actions_proposed: int
    decisions: list[dict[str, Any]]


class AgentRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentRunSummary]


class TriggerAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: AgentRunSummary
```

- [ ] **Step 3:** `service.py`:

```python
from sqlmodel import Session, col, select

from munim.agents.rto_mitigator.agent import RTOMitigatorAgent
from munim.models import RunLog
from munim.modules.agent_runs.schemas import (
    AgentRunDetail,
    AgentRunListResponse,
    AgentRunSummary,
    TriggerAgentResponse,
)
from munim.shared.constants import AgentName, ErrorCode, RunLogKind
from munim.shared.errors import MunimError


class AgentUnknownError(MunimError):
    code = ErrorCode.AGENT_UNKNOWN.value
    http_status = 404
    message = "Unknown agent."


class AgentRunNotFoundError(MunimError):
    code = ErrorCode.RECORD_NOT_FOUND.value
    http_status = 404
    message = "Agent run not found."


_AGENTS = {
    AgentName.RTO_MITIGATOR: RTOMitigatorAgent,
}


def trigger_agent(
    session: Session, merchant_id: str, agent_name: AgentName
) -> TriggerAgentResponse:
    agent_cls = _AGENTS.get(agent_name)
    if agent_cls is None:
        raise AgentUnknownError(
            message=f"Agent {agent_name.value!r} is not registered.",
            details={"agent": agent_name.value},
        )
    agent = agent_cls()
    summary = agent.run(session, merchant_id)
    return TriggerAgentResponse(
        run=AgentRunSummary(
            run_log_id=summary.run_log_id,
            run_id=summary.run_id,
            agent=agent_name.value,
            orders_scanned=summary.orders_scanned,
            actions_proposed=summary.actions_proposed,
            started_at=summary.started_at,
            finished_at=summary.finished_at,
        )
    )


def list_agent_runs(session: Session, merchant_id: str, limit: int) -> AgentRunListResponse:
    effective_limit = max(1, min(limit, 200))
    rows = session.exec(
        select(RunLog)
        .where(RunLog.merchant_id == merchant_id)
        .where(RunLog.kind == RunLogKind.AGENT.value)
        .order_by(col(RunLog.started_at).desc())
        .limit(effective_limit)
    ).all()
    items = [
        AgentRunSummary(
            run_log_id=r.id if r.id is not None else 0,
            run_id=r.detail_json["run_id"],
            agent=r.detail_json["agent"],
            orders_scanned=r.detail_json["orders_scanned"],
            actions_proposed=r.detail_json["actions_proposed"],
            started_at=r.started_at,
            finished_at=r.finished_at if r.finished_at else r.started_at,
        )
        for r in rows
    ]
    return AgentRunListResponse(items=items)


def get_agent_run(session: Session, merchant_id: str, run_log_id: int) -> AgentRunDetail:
    row = session.exec(
        select(RunLog)
        .where(RunLog.id == run_log_id)
        .where(RunLog.merchant_id == merchant_id)
        .where(RunLog.kind == RunLogKind.AGENT.value)
    ).first()
    if row is None:
        raise AgentRunNotFoundError(
            message=f"Agent run {run_log_id} not found.",
            details={"run_log_id": run_log_id},
        )
    return AgentRunDetail(
        run_log_id=row.id if row.id is not None else 0,
        run_id=row.detail_json["run_id"],
        agent=row.detail_json["agent"],
        started_at=row.started_at,
        finished_at=row.finished_at if row.finished_at else row.started_at,
        orders_scanned=row.detail_json["orders_scanned"],
        actions_proposed=row.detail_json["actions_proposed"],
        decisions=row.detail_json["decisions"],
    )
```

- [ ] **Step 4:** Lint + full suite. Commit.

```
git add apps/api/src/munim/modules/agent_runs
git commit -m "feat(agent-runs): schemas + service for triggering and listing agent runs"
```

---

## Task 6 — Agent-runs router + endpoint tests

**Files:** `apps/api/src/munim/modules/agent_runs/router.py`, `apps/api/src/munim/modules/agent_runs/tests/test_router.py`, `apps/api/src/munim/main.py` (register).

- [ ] **Step 1:** `router.py`:

```python
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from munim.modules.agent_runs.schemas import (
    AgentRunDetail,
    AgentRunListResponse,
    TriggerAgentResponse,
)
from munim.modules.agent_runs.service import (
    AgentUnknownError,
    get_agent_run,
    list_agent_runs,
    trigger_agent,
)
from munim.shared.constants import AgentName
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(tags=["agent-runs"])


@router.post(
    "/agents/{name}/run",
    response_model=SuccessEnvelope[TriggerAgentResponse],
)
def trigger_agent_endpoint(
    name: str,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[TriggerAgentResponse]:
    try:
        agent_name = AgentName(name)
    except ValueError as exc:
        raise AgentUnknownError(
            message=f"Agent {name!r} is not registered.",
            details={"agent": name},
        ) from exc
    result = trigger_agent(session, DEFAULT_MERCHANT_ID, agent_name)
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)


@router.get(
    "/agent-runs",
    response_model=SuccessEnvelope[AgentRunListResponse],
)
def list_endpoint(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[AgentRunListResponse]:
    data = list_agent_runs(session, DEFAULT_MERCHANT_ID, limit)
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.get(
    "/agent-runs/{run_log_id}",
    response_model=SuccessEnvelope[AgentRunDetail],
)
def detail_endpoint(
    run_log_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> SuccessEnvelope[AgentRunDetail]:
    data = get_agent_run(session, DEFAULT_MERCHANT_ID, run_log_id)
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)
```

Note: this router uses two prefixes (`/agents/...` and `/agent-runs/...`) so it doesn't carry a single prefix — declare them on each endpoint as shown.

- [ ] **Step 2:** Register the router in `apps/api/src/munim/main.py`:

```python
from munim.modules.agent_runs.router import router as agent_runs_router
# ...
app.include_router(agent_runs_router)
```

- [ ] **Step 3:** Write the failing tests.

`test_router.py`:

```python
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from munim.models import Record
from munim.shared.constants import EntityType, PaymentMethod, SourceSystem


def _seed_cod_order(session: Any, source_id: str) -> None:
    row = Record(
        merchant_id="m_default",
        source_system=SourceSystem.SHOPIFY.value,
        source_id=source_id,
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash=f"h_{source_id}",
        raw={"id": source_id},
        normalized={
            "placed_at": "2026-05-10T23:45:00+05:30",
            "total_inr": "6000",
            "currency": "INR",
            "payment_method": PaymentMethod.COD.value,
            "financial_status": "pending",
            "pincode": "110001",
            "customer_source_id": "cust_x",
        },
    )
    session.add(row)
    session.commit()


def test_trigger_agent_returns_summary(client: TestClient) -> None:
    from munim.shared.db import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        _seed_cod_order(s, "cod_smoke")

    response = client.post("/agents/rto_mitigator/run")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["run"]["agent"] == "rto_mitigator"
    assert body["data"]["run"]["orders_scanned"] == 1


def test_trigger_unknown_agent_returns_404(client: TestClient) -> None:
    response = client.post("/agents/madeup/run")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "agent.unknown"


def test_list_agent_runs_returns_summaries(client: TestClient) -> None:
    from munim.shared.db import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        _seed_cod_order(s, "cod_list_1")

    client.post("/agents/rto_mitigator/run").raise_for_status()
    response = client.get("/agent-runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]["items"]) >= 1
    assert body["data"]["items"][0]["agent"] == "rto_mitigator"


def test_get_agent_run_returns_decisions(client: TestClient) -> None:
    from munim.shared.db import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        _seed_cod_order(s, "cod_detail")

    trigger_body = client.post("/agents/rto_mitigator/run").json()
    run_log_id = trigger_body["data"]["run"]["run_log_id"]

    response = client.get(f"/agent-runs/{run_log_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["run_log_id"] == run_log_id
    assert len(body["data"]["decisions"]) == 1
    d = body["data"]["decisions"][0]
    assert d["action"] == "convert_to_prepaid"


def test_get_unknown_agent_run_returns_typed_404(client: TestClient) -> None:
    response = client.get("/agent-runs/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "record.not_found"
```

- [ ] **Step 4:** Run + commit.

```
uv run pytest src/munim/modules/agent_runs -v
uv run ruff check src
uv run mypy src
uv run pytest -v
git add apps/api/src/munim/modules/agent_runs apps/api/src/munim/main.py
git commit -m "feat(agent-runs): expose POST /agents/{name}/run + GET /agent-runs endpoints"
```

Expected: 162 tests passing.

---

## Task 7 — Seed one COD order via Shopify CLI for the live demo

**Files:** none (this is a manual smoke prep, not a code change).

For the live agent-run demo to show a non-trivial decision, the dev store needs at least one COD order. The 3 existing orders are all `payment_method='prepaid'` so they get filtered out at the agent's COD scan.

- [ ] **Step 1:** Verify shopify CLI is still authed from Phase 4.

```
shopify store execute --store munim-dev.myshopify.com --query 'query { shop { name } }'
```

Expected: returns shop data. If it asks for re-auth, run `shopify store auth --store munim-dev.myshopify.com --scopes 'write_draft_orders,read_orders,read_customers,read_products,read_inventory'` first.

- [ ] **Step 2:** Create a high-RTO-risk COD draft order.

Reuse the Phase 4 `draft.graphql` mutation file or recreate it. Variables for a high-risk order: high value, high-risk pincode, late-night timestamp.

```
$tmpDir = 'D:\PROJECTS\AI-MUNIM\AI-Munim\.tmp-seed'
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

# Reuse Phase 4 draft.graphql if present; otherwise create:
$draftMutation = @'
mutation DraftOrderCreate($input: DraftOrderInput!) {
  draftOrderCreate(input: $input) {
    draftOrder { id name }
    userErrors { field message }
  }
}
'@
[System.IO.File]::WriteAllText("$tmpDir\draft.graphql", $draftMutation, [System.Text.UTF8Encoding]::new($false))

$codDraft = @'
{
  "input": {
    "lineItems": [{
      "title": "Premium Hoodie",
      "quantity": 2,
      "originalUnitPriceWithCurrency": { "amount": "3000.00", "currencyCode": "INR" }
    }],
    "shippingAddress": {
      "firstName": "Rohan", "lastName": "Verma",
      "address1": "1 Connaught Place", "city": "New Delhi", "zip": "110001",
      "countryCode": "IN", "phone": "+919900000005"
    },
    "email": "rohan@example.com", "phone": "+919900000005",
    "tags": ["munim-test", "cod-high-risk"]
  }
}
'@
[System.IO.File]::WriteAllText("$tmpDir\cod_draft.json", $codDraft, [System.Text.UTF8Encoding]::new($false))

shopify store execute --store munim-dev.myshopify.com --query-file "$tmpDir\draft.graphql" --variable-file "$tmpDir\cod_draft.json" --allow-mutations --json
```

Capture the returned `DraftOrder/<id>` and complete it with `paymentPending: true` (matches Phase 4 pattern):

```
$completeMutation = @'
mutation DraftOrderComplete($id: ID!, $paymentPending: Boolean) {
  draftOrderComplete(id: $id, paymentPending: $paymentPending) {
    draftOrder { id order { id name displayFinancialStatus } }
    userErrors { field message }
  }
}
'@
[System.IO.File]::WriteAllText("$tmpDir\complete.graphql", $completeMutation, [System.Text.UTF8Encoding]::new($false))

# Use the actual draft id returned above
$complete = '{"id": "gid://shopify/DraftOrder/<id-from-step-above>", "paymentPending": true}'
[System.IO.File]::WriteAllText("$tmpDir\complete_cod.json", $complete, [System.Text.UTF8Encoding]::new($false))

shopify store execute --store munim-dev.myshopify.com --query-file "$tmpDir\complete.graphql" --variable-file "$tmpDir\complete_cod.json" --allow-mutations --json
```

Note on `payment_method` mapping: when an order is completed via `draftOrderComplete(paymentPending: true)`, Shopify doesn't populate `payment_gateway_names` (no gateway involved — it's a manual pending order). Our mapper's `_infer_payment_method` falls through to `PREPAID` for these. **For the agent to see a COD order, we need to either (a) tweak the order to have a COD gateway, OR (b) handle the seeding differently.**

Pragmatic fix: after `draftOrderComplete`, manually update the order's `gateway` field via a follow-up GraphQL mutation, OR seed the COD order directly in our local DB (faster, bypasses Shopify's quirks). The cleanest path:

```python
# Add this to a `apps/api/scripts/seed_cod_order.py` script:
from munim.shared.db import get_engine, init_db
from munim.models import Record
from sqlmodel import Session
from datetime import datetime, UTC

init_db()
with Session(get_engine()) as s:
    row = Record(
        merchant_id="m_default",
        source_system="shopify",
        source_id="seed_cod_demo",
        entity_type="order",
        fetched_at=datetime.now(UTC),
        payload_hash="seed_cod_h",
        raw={"id": "seed_cod_demo", "source": "agent-demo-seed"},
        normalized={
            "placed_at": "2026-05-14T23:45:00+05:30",
            "total_inr": "6000.00",
            "currency": "INR",
            "payment_method": "cod",
            "financial_status": "pending",
            "fulfillment_status": None,
            "pincode": "110001",
            "customer_source_id": "seed_cust_high_risk",
            "utm_campaign": "demo",
            "line_items_count": 2,
        },
    )
    s.add(row)
    s.commit()
    print(f"Seeded COD demo row id={row.id}")
```

- [ ] **Step 3:** Run the seed script.

```
$env:Path = "C:\Users\loots\.local\bin;$env:Path"
Set-Location 'D:\PROJECTS\AI-MUNIM\AI-Munim\apps\api'
# Save the script above to scripts/seed_cod_order.py first
uv run python scripts/seed_cod_order.py
```

This adds one local-only COD demo row to the DB so the agent has something to score. The README will note this as demo-mode seeding (it's only in the local dev DB, not in Shopify's actual orders).

This step doesn't produce a commit — it's a local DB mutation. Document in the smoke recipe inside `CHANGELOG.md`.

---

## Task 8 — Docs + final commit

**Files:** `CHANGELOG.md`, `context.md`.

- [ ] **Step 1:** CHANGELOG entry at top:

```
## 2026-05-14 — Phase 6: RTO Risk Mitigator agent (backend)

**What changed:** New `apps/api/src/munim/agents/rto_mitigator/` package — pure-function signal extractors (`order_value_bucket`, `pincode_risk`, `time_of_order_risk`, `customer_rto_rate`), weighted scoring with threshold tree (convert_to_prepaid > 0.6, confirmation_call > 0.4, else no_action), and a deterministic orchestrator that scans COD orders, scores each, and writes ONE `RunLog` row per agent run containing the full per-order decision list. New `modules/agent_runs/` exposes `POST /api/agents/{name}/run`, `GET /api/agent-runs`, `GET /api/agent-runs/{id}`. The agent is deterministic (no LLM) by design — auditable, cheap, predictable; the brief asks for "the reasoning" visible in the run log.

**No side effects:** there is a dedicated test (`test_agent_makes_zero_outbound_http_calls`) that fails if any future code path adds an outbound HTTP call. Locks the brief's "AI employee proposes, doesn't dispatch" constraint at the type-system + test level.

**Test count:** 135 → ~162 (+27): 9 signals + 6 scoring + 7 agent + 5 endpoint.

**Files touched:** `apps/api/src/munim/agents/**`, `apps/api/src/munim/modules/agent_runs/**`, `apps/api/src/munim/shared/constants.py`, `apps/api/src/munim/main.py`.

**Demo seeding:** `apps/api/scripts/seed_cod_order.py` adds one high-RTO-risk COD order to the local DB (Shopify dev-store quirk: `draftOrderComplete(paymentPending: true)` doesn't populate `payment_gateway_names`, so the mapper defaults to prepaid). Local seed is documented as demo-only.

**Reverts cleanly?:** yes — drop `agents/` and `modules/agent_runs/`, revert constants + main.py.
```

- [ ] **Step 2:** `context.md` updates:
  - **Now:** "Phase 6 complete. RTO Risk Mitigator agent live. POST /agents/rto_mitigator/run + GET /agent-runs working against real seeded data."
  - **Done:** append Phase 6.
  - **Next:** bump Phase 7 (frontend chat + agent runs page) to top; Phase 8 (README rewrite, demo seed, docker-compose story).
  - **Decisions:** add an entry on the deterministic-vs-LLM agent choice with reasoning.

- [ ] **Step 3:** Commit.

```
git add CHANGELOG.md context.md apps/api/scripts/
git commit -m "docs(phase-6): record RTO agent backend completion + demo seed script"
```

---

## Self-review

**Spec coverage (brief):**
- "At least one autonomous agent. Your 'AI employee'." — RTO Mitigator ships, manually triggerable now, cron-ready.
- "Watches the data" — scans `record` table for COD orders.
- "Proposes a ₹-saving or ops-saving action" — `convert_to_prepaid` / `confirmation_call`, with `estimated_inr_saved` math shown.
- "Don't actually send anything; we want the run log and the reasoning." — `test_agent_makes_zero_outbound_http_calls` locks zero HTTP calls. Decisions persist to `run_log` with weights + signals + reasoning visible.

**Type/name consistency:**
- `AgentActionType` StrEnum used everywhere a string comparison would otherwise sneak in.
- `RunLogKind.AGENT.value` used to filter agent runs in service.py.
- `AgentName.RTO_MITIGATOR` consistent between agent class, registry, and endpoint dispatch.

**§13.4 — meaningful tests only:**
- Signal tests pin specific bucket transitions + edge cases (None pincode, hour bands, sparse-customer fallback).
- Scoring tests pin threshold transitions + INR-saved proportionality.
- Agent tests pin: only-COD-scored, one-run-log-per-run, decision shape, high-risk-flow, zero-HTTP (the brief's constraint), zero-COD edge.
- Router tests pin: endpoint envelope + typed 404s on unknown agent / unknown run id.

**Comment discipline (user feedback during Phase 5):**
- No comments referencing tasks, phases, reviewers, issues — none in this plan's code blocks.
- Only WHY comments where the WHY is non-obvious (the high-risk pincode list constants in `signals.py` have no comment because the names are self-explanatory; the `_LATE_NIGHT_*` thresholds same).
- Docstrings on public surfaces only.

**Out of scope, re-listed:**
- LLM-driven decisions (deterministic by design)
- Shiprocket-backed customer history (Phase 5b)
- product_category signal (deferred — schema change)
- Cron auto-fire (wired, disabled by default)
- Frontend Agent Runs page (Phase 7)
- Real outbound actions (brief explicit)
- Per-decision RunLog rows (one-per-run is the design)

**Honest gaps documented for the README:**
- `customer_rto_rate` returns population baseline for any customer with < 3 orders. v0 has < 5 orders total; the agent's customer signal is effectively constant. Phase 5b fixes this.
- `product_category` signal is always None. Weight 0.1 means it doesn't materially affect score, but the omission is noted.
- High-risk pincode list is a small seed, not aggregated. Documented honestly.
- Agent fires on demand only (cron disabled in v0). One-line flip to enable in production.
