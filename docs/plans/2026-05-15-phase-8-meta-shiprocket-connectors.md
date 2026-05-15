# Phase 8 — Meta Ads + Shiprocket Connectors (Demo-Mode) Implementation Plan

> **For agentic workers:** ONE subagent dispatch for the whole phase. 6 tasks top-to-bottom, commit per task, report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Use `superpowers:subagent-driven-development`.
>
> **Comment discipline (Phases 5–7 paid lesson):** default to NO comments. WHY-only when non-obvious. NEVER task/phase/reviewer-referential. NEVER narrate what well-named code does.
>
> **API contracts (Phase 7 paid lesson):** every shape this plan claims about a provider's API was verified against their public docs while writing. The implementer should still cross-check by opening the fixture file and the provider's docs side-by-side before writing the mapper.
>
> **Phase numbering note:** earlier `context.md → Next` had "Phase 8 = polish, Phase 9 = connectors." Connectors block the brief's hard "≥3" requirement; polish doesn't. We swapped the order. This file is Phase 8 (chronologically the 8th plan); polish follows as Phase 9.

**Goal:** Bring the project to **3 connectors behind one abstraction** (the brief's hard requirement) by adding Meta Ads and Shiprocket as demo-mode connectors alongside the real Shopify OAuth path. Both new connectors sit behind the existing `BaseConnector` ABC, route through `RowSink`, and write to the universal `record` table. Demo data is curated to make the RTO agent's `customer_rto_rate` signal fire meaningfully (customer A with high RTO history → `convert_to_prepaid`; customer B with clean history → `no_action`) and to give the chat real numbers to ground answers in.

**Architecture:**
- Two new backend connector packages under `apps/api/src/munim/connectors/`:
  - `meta_ads/` — `mapper.py`, `connector.py`, `fixtures/insights.json` (~40 real-shape campaign-day rows from Meta Marketing API).
  - `shiprocket/` — `mapper.py`, `connector.py`, `fixtures/shipments.json` (~50 rows, real Shiprocket API shape, deliberately curated RTO distribution).
- Both connectors implement `BaseConnector` identically to Shopify — same `sync()` contract, same `RowSink` writer, same `RunLog` emission. The only difference: `sync()` reads from the fixture file rather than calling an HTTP client. **The abstraction is what's being graded; the data source is implementation detail.**
- Demo-mode is labeled in code (`is_demo = True` class attribute) and surfaced through the connectors-list endpoint, so the UI can render a "demo" badge. Honest scope, never hidden.
- New endpoint `POST /connectors/{name}/connect-demo` performs a one-click connect: validates the connector exists and is demo-mode, upserts a `connector_credentials` row with `status=CredentialStatus.DEMO` and an empty blob (no secret to store), returns success.
- RTO agent's `customer_rto_rate` signal rewires: instead of querying order records (which never carry `fulfillment_status` — they can't, that's a shipment lifecycle attribute), it queries shipment records from Shiprocket. The mapper attaches a stable `customer_source_id` (SHA-256 hash of `email|phone`, first 16 hex chars) so the agent can join customer histories.

**Tech stack additions:** none. Everything reuses existing httpx/cryptography/structlog/sqlmodel/Pydantic.

**Out of scope (deliberate, documented in README):**
- **Real Shiprocket API integration.** Shiprocket has no sandbox; the free production tier starts empty. Forcing a real account through the demo would require ~30–45 min of manual order creation and still wouldn't produce realistic RTO statuses (those are end-states of real shipment lifecycle, not API-writable). Demo-mode with real-shape fixtures is the honest scope choice.
- **Real Meta Ads OAuth.** Facebook Business Manager + Ad Account permission setup is ~1h of FB-portal friction per evaluator with zero benefit if their ad account has no spend. Demo-mode with real-shape `/insights` fixtures gives the abstraction without the tax.
- **Webhook ingestion.** Polling-sync via `POST /connectors/{name}/sync` is the v0 pattern.
- **Per-customer chat queries that span Shopify + Shiprocket data.** Possible (both connectors share `customer_source_id`) but not specifically wired into a chat tool. The data is there; future chat enhancements can query across.

**Time budget:** ~6h dev + reviewer cycle. Leaves ~45h for Phase 9 (README + docker-compose + final polish).

---

## File map

**New (backend):**
- `apps/api/src/munim/connectors/meta_ads/__init__.py`
- `apps/api/src/munim/connectors/meta_ads/mapper.py`
- `apps/api/src/munim/connectors/meta_ads/connector.py`
- `apps/api/src/munim/connectors/meta_ads/fixtures/insights.json`
- `apps/api/src/munim/connectors/meta_ads/tests/__init__.py`
- `apps/api/src/munim/connectors/meta_ads/tests/test_mapper.py`
- `apps/api/src/munim/connectors/meta_ads/tests/test_connector.py`
- `apps/api/src/munim/connectors/shiprocket/__init__.py`
- `apps/api/src/munim/connectors/shiprocket/mapper.py`
- `apps/api/src/munim/connectors/shiprocket/connector.py`
- `apps/api/src/munim/connectors/shiprocket/fixtures/shipments.json`
- `apps/api/src/munim/connectors/shiprocket/tests/__init__.py`
- `apps/api/src/munim/connectors/shiprocket/tests/test_mapper.py`
- `apps/api/src/munim/connectors/shiprocket/tests/test_connector.py`
- `apps/api/src/munim/modules/connectors/demo_connect.py` (new endpoint + tests)
- `apps/api/src/munim/modules/connectors/tests/test_demo_connect.py`

**New (frontend):**
- `apps/web/src/modules/connectors/components/EnableDemoButton.tsx`

**Modified (backend):**
- `apps/api/src/munim/connectors/base.py` — add `is_demo: bool = False` class attribute to `BaseConnector`.
- `apps/api/src/munim/connectors/registry.py` — register both new connectors.
- `apps/api/src/munim/shared/constants.py` — verify `SourceSystem.META_ADS`, `SourceSystem.SHIPROCKET`, `ConnectorName.META_ADS`, `ConnectorName.SHIPROCKET` exist (they do from Phase 2). Verify `CredentialStatus.DEMO` exists (it does). Verify `FulfillmentStatus` enum is complete; add `IN_TRANSIT` if missing.
- `apps/api/src/munim/modules/connectors/router.py` — wire the demo-connect endpoint.
- `apps/api/src/munim/modules/connectors/schemas.py` — surface `is_demo` on the connector list response.
- `apps/api/src/munim/agents/rto_mitigator/signals.py` — `customer_rto_rate` reads shipment records.
- `apps/api/src/munim/agents/rto_mitigator/tests/test_signals.py` — new fixtures + assertions for the shipment-driven path.

**Modified (frontend):**
- `apps/web/src/modules/connectors/api/client.ts` — Zod schema picks up `is_demo` field; add `connectDemo(name)` fetcher.
- `apps/web/src/modules/connectors/components/ConnectorCard.tsx` (or wherever the per-connector CTA lives) — branch on `is_demo`: render `EnableDemoButton` for demo connectors, existing OAuth flow for Shopify.

---

## Task 1 — Meta Ads demo connector: fixture + mapper + connector + tests

**Files:** `connectors/meta_ads/{__init__,mapper,connector}.py`, `fixtures/insights.json`, `tests/`, register in `registry.py`.

- [ ] **Step 1:** Build `fixtures/insights.json`. ~40 rows: 4 campaigns × 10 days. Real Meta Marketing API `/insights` shape:

```json
{
  "data": [
    {
      "campaign_id": "23847264829340001",
      "campaign_name": "Spring Sale - Hoodies",
      "date_start": "2026-04-15",
      "date_stop": "2026-04-15",
      "spend": "1245.67",
      "impressions": "45678",
      "clicks": "892",
      "ctr": "1.95",
      "cpm": "27.27",
      "actions": [
        {"action_type": "purchase", "value": "12"},
        {"action_type": "add_to_cart", "value": "47"}
      ]
    }
  ]
}
```

Campaign names should be realistic D2C brand language ("Spring Sale - Hoodies", "Retargeting - Cart Abandoners", "New Drop - Sneakers", "Diwali Push"). Spend distribution: 1 campaign at ₹1k-2k/day (high), 1 at ₹500-1k (mid), 2 at ₹100-500 (small/exploratory). CTR 1–4% range, realistic. Purchase counts: bigger campaigns have more purchases, ROAS varies.

- [ ] **Step 2:** `mapper.py`. Each row becomes:

```python
{
  "source_system": SourceSystem.META_ADS.value,
  "source_id": f"{campaign_id}_{date_start}",
  "entity_type": EntityType.AD_SPEND.value,
  "normalized": {
    "campaign_id": "...",
    "campaign_name": "...",
    "date": "2026-04-15",
    "spend_inr": "1245.67",
    "impressions": 45678,
    "clicks": 892,
    "ctr": 1.95,
    "cpm": 27.27,
    "purchases_attributed": 12,
    "add_to_carts_attributed": 47,
  }
}
```

Notes:
- `actions` array is positional; extract `purchase` and `add_to_cart` by `action_type`. Missing → 0.
- `spend_inr` is `Decimal`-as-string per §8.1. If the input can't parse as Decimal, raise `UnexpectedSpendValueError` (typed). No silent coercion.
- `date` is a date string, not a UTC timestamp — campaign-day spend is naturally date-bucketed, no time component. Document this once on the function so a future reviewer doesn't conflate it with order timestamps.

Tests cover: shape correctness, `actions` extraction with missing types, malformed spend raises typed error, source_id composite key.

- [ ] **Step 3:** `connector.py`. `MetaAdsConnector(BaseConnector)`:

```python
class MetaAdsConnector(BaseConnector):
    name = ConnectorName.META_ADS
    source_system = SourceSystem.META_ADS
    is_demo = True

    async def sync(self, session: Session, merchant_id: str) -> SyncResult:
        await asyncio.sleep(0.2)  # so the UI "Syncing…" state isn't a flash
        fixture_path = Path(__file__).parent / "fixtures" / "insights.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        rows = [map_meta_ads_insight(raw, merchant_id) for raw in payload["data"]]
        sink = RowSink(session)
        result = sink.upsert_records(rows)
        # RunLog write same as Shopify connector
        ...
        return result
```

Idempotency: `payload_hash` over `(campaign_id, date_start, spend)` → re-syncs are no-ops.

Tests cover: end-to-end sync writes the right number of `record` rows + a `run_log` entry, idempotent re-sync writes no new rows.

- [ ] **Step 4:** Register in `registry.py`. Lint + full suite. Commit.

```
git commit -m "feat(meta-ads): demo connector with 40-row insights fixture + ad_spend mapper"
```

---

## Task 2 — Shiprocket demo connector: fixture + mapper + connector + tests

**Files:** `connectors/shiprocket/{__init__,mapper,connector}.py`, `fixtures/shipments.json`, `tests/`, register in `registry.py`.

- [ ] **Step 1:** Build `fixtures/shipments.json`. ~50 rows in real Shiprocket `/v1/external/orders` shape. **The fixture is deliberately curated for demo:**

- **Customer A** (`rohan@example.com`): 5 shipments → 3 `RTO`, 2 `DELIVERED`. **High-risk customer.** Agent's `customer_rto_rate` will return 1.0 (saturated). Combined with a new ₹6000 COD order from this customer, the agent should decide `convert_to_prepaid`.
- **Customer B** (`priya@example.com`): 5 shipments → 5 `DELIVERED`. **Clean record.** Agent's `customer_rto_rate` returns 0.0. The same ₹6000 COD order from this customer would still hit other risk signals (pincode, time-of-day, value) but customer signal stays clean.
- **Customer C** (`amit@example.com`): 5 shipments → 1 `RTO`, 4 `DELIVERED`. **Mid-risk** (20% rate, same as population baseline). Demonstrates the "confident but unremarkable" branch.
- Remaining ~35 shipments: 30 unique customers with 1–2 shipments each, mixed statuses (mostly DELIVERED, scattered RTO/IN-TRANSIT/CANCELLED). Provides the chat with "how many shipments did I RTO last week" kind of data without distorting the agent demo.

Real Shiprocket row shape:

```json
{
  "id": 12345678,
  "channel_order_id": "1001",
  "customer_email": "rohan@example.com",
  "customer_phone": "+919900000005",
  "status": "DELIVERED",
  "awb_code": "SR9876543210",
  "courier_name": "Delhivery Surface",
  "total": "1500.00",
  "created_at": "2026-04-15 10:30:00",
  "shipping_address": {"pincode": "110001"}
}
```

- [ ] **Step 2:** `mapper.py`. Maps each row to:

```python
{
  "source_system": SourceSystem.SHIPROCKET.value,
  "source_id": str(shiprocket_id),
  "entity_type": EntityType.SHIPMENT.value,
  "normalized": {
    "channel_order_id": "1001",            # link back to Shopify order
    "customer_source_id": sha256_hex_first16(email or phone),
    "fulfillment_status": FulfillmentStatus.<X>.value,
    "awb_code": "SR9876543210",
    "courier_name": "Delhivery Surface",
    "total_inr": "1500.00",
    "placed_at": utc_iso(created_at_ist),   # convert IST naive → UTC ISO 8601
    "pincode": "110001",
  }
}
```

Notes:
- `customer_source_id` hashing rule: prefer email if present, else phone, else raise `MissingCustomerIdentityError`. SHA-256 → first 16 hex chars. Stable, privacy-preserving, hash-collision-acceptable for v0.
- Status map: `DELIVERED → FULFILLED`, `RTO → RTO`, `"RTO INITIATED" → RTO`, `IN-TRANSIT → IN_TRANSIT` (add this enum value if missing), `"PICKUP SCHEDULED" → PENDING`, `CANCELED → CANCELLED`, `CANCELLED → CANCELLED`. Unknown status → `UnknownShipmentStatusError` (typed). No silent buckets.
- Shiprocket `created_at` is IST-naive ("2026-04-15 10:30:00"). Parse, attach `ZoneInfo("Asia/Kolkata")`, convert to UTC. **Past lesson (Phase 6 review):** never read clock fields off the wire-format value; always convert at the boundary.

Tests cover: status enum coverage, IST→UTC conversion, customer hash stability across email/phone preference order, missing identity raises typed error, unknown status raises typed error.

- [ ] **Step 3:** `connector.py`. `ShiprocketConnector(BaseConnector)` mirrors `MetaAdsConnector` exactly: `is_demo = True`, `sync()` reads fixture, sinks via `RowSink`, writes `RunLog`. Same 200ms sleep so the UI state has perceptible weight.

Tests: end-to-end sync produces the expected ~50 shipment records, idempotent re-sync, run_log row carries correct counts.

- [ ] **Step 4:** Register in `registry.py`. Lint + full suite. Commit.

```
git commit -m "feat(shiprocket): demo connector with curated shipments fixture + shipment mapper"
```

---

## Task 3 — Generic demo-connect endpoint

**Files:** `apps/api/src/munim/modules/connectors/demo_connect.py`, register in `router.py`, `tests/test_demo_connect.py`. Also modify `BaseConnector` to add the `is_demo` attribute (Task 1 introduces; this task formalizes), and `schemas.py` to surface it on the connector list response.

- [ ] **Step 1:** Add `is_demo: ClassVar[bool] = False` to `BaseConnector` in `connectors/base.py`. Document in a one-line docstring (genuine WHY-comment, this is a contract).

- [ ] **Step 2:** Update `connector_summary_schema` (or wherever the connectors-list serializes per-connector) to include `is_demo: bool`. The `GET /connectors` response now ships the flag.

- [ ] **Step 3:** New `demo_connect.py`:

```python
@router.post("/connectors/{name}/connect-demo", response_model=SuccessEnvelope[ConnectorStatusResponse])
async def connect_demo(name: str, request: Request, session: Session = Depends(get_session)) -> ...:
    try:
        connector_name = ConnectorName(name)
    except ValueError as exc:
        raise ConnectorUnknownError(...) from exc
    connector_cls = REGISTRY.get(connector_name)
    if connector_cls is None or not connector_cls.is_demo:
        raise ConnectorNotDemoError(
            message=f"Connector {name!r} is not a demo connector.",
            details={"connector": name},
        )
    # Upsert credentials row with status=DEMO and empty blob
    upsert_credentials(
        session, merchant_id=DEFAULT_MERCHANT_ID, connector_name=connector_name,
        encrypted_blob=b"", status=CredentialStatus.DEMO,
    )
    session.commit()
    return SuccessEnvelope(data=ConnectorStatusResponse(status="connected"), trace_id=request.state.trace_id)
```

Add `ErrorCode.CONNECTOR_NOT_DEMO = "connector.not_demo"` if not already present; create `ConnectorNotDemoError` (typed, HTTP 400).

- [ ] **Step 4:** Tests:

```python
def test_connect_demo_writes_credentials_row_with_demo_status(client, session):
    resp = client.post("/connectors/meta_ads/connect-demo")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "connected"
    # session shows a credentials row with status=demo
    ...


def test_connect_demo_rejects_non_demo_connector(client):
    resp = client.post("/connectors/shopify/connect-demo")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "connector.not_demo"


def test_connect_demo_rejects_unknown_connector(client):
    resp = client.post("/connectors/madeup/connect-demo")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "connector.unknown"
```

- [ ] **Step 5:** Lint + full suite. Commit.

```
git commit -m "feat(connectors): POST /connectors/{name}/connect-demo + is_demo on BaseConnector"
```

---

## Task 4 — Rewire RTO agent: customer_rto_rate uses Shiprocket shipments

**Files:** `agents/rto_mitigator/signals.py`, `tests/test_signals.py`.

Old behavior: queried `record` where `entity_type=order` AND counted `fulfillment_status=rto`. Always 0 in practice — order rows don't carry that field; it's a shipment lifecycle attribute. New behavior: query `record` where `entity_type=shipment` AND `source_system=shiprocket`, filter by `customer_source_id`, count `fulfillment_status=rto`.

- [ ] **Step 1:** Update `test_signals.py`. Add `_seed_shipment` helper. New assertions:

```python
def test_customer_rto_rate_uses_shipments_not_orders(session):
    for i in range(5):
        _seed_shipment(
            session,
            source_id=f"sr_{i}",
            customer_source_id="cust_a_hash",
            fulfillment_status=(
                FulfillmentStatus.RTO.value if i < 3 else FulfillmentStatus.FULFILLED.value
            ),
        )
    session.commit()
    result = customer_rto_rate(session, "m_default", "cust_a_hash")
    assert result.diagnostic["history_count"] == 5
    assert result.diagnostic["rto_count"] == 3
    assert result.diagnostic["rate_source"] == "customer_history"
    assert result.diagnostic["confident"] is True
    assert result.score == 1.0  # min(0.6 * 1.5, 1.0)


def test_customer_rto_rate_ignores_non_shiprocket_records(session):
    for i in range(5):
        _seed_order_with_fulfillment(
            session, customer_source_id="cust_a_hash", fulfillment_status=FulfillmentStatus.RTO.value,
        )
    session.commit()
    result = customer_rto_rate(session, "m_default", "cust_a_hash")
    assert result.diagnostic["history_count"] == 0  # no shipment records
    assert result.score == _POPULATION_RTO_BASELINE


def test_customer_rto_rate_with_few_shipments_returns_baseline(session):
    for i in range(2):
        _seed_shipment(
            session, source_id=f"sr_{i}", customer_source_id="cust_b_hash",
            fulfillment_status=FulfillmentStatus.RTO.value,
        )
    session.commit()
    result = customer_rto_rate(session, "m_default", "cust_b_hash")
    assert result.diagnostic["history_count"] == 2
    assert result.diagnostic["confident"] is False
    assert result.score == _POPULATION_RTO_BASELINE
```

- [ ] **Step 2:** Update `customer_rto_rate` in `signals.py`:

```python
def customer_rto_rate(
    session: Session,
    merchant_id: str,
    customer_source_id: str | None,
) -> SignalResult:
    if not customer_source_id:
        return SignalResult(
            score=_POPULATION_RTO_BASELINE,
            diagnostic={"history_count": 0, "confident": False, "rate_source": "population_baseline", "customer_id_missing": True},
        )
    rows = session.exec(
        select(Record)
        .where(Record.merchant_id == merchant_id)
        .where(Record.source_system == SourceSystem.SHIPROCKET.value)
        .where(Record.entity_type == EntityType.SHIPMENT.value)
    ).all()
    customer_rows = [r for r in rows if r.normalized.get("customer_source_id") == customer_source_id]
    history_count = len(customer_rows)
    confident = history_count >= _CONFIDENT_HISTORY_MIN
    if not confident:
        return SignalResult(
            score=_POPULATION_RTO_BASELINE,
            diagnostic={"history_count": history_count, "confident": False, "rate_source": "population_baseline"},
        )
    rto_count = sum(
        1 for r in customer_rows if r.normalized.get("fulfillment_status") == FulfillmentStatus.RTO.value
    )
    rate = rto_count / history_count
    return SignalResult(
        score=min(rate * _RTO_RATE_SIGNAL_MULTIPLIER, 1.0),
        diagnostic={
            "history_count": history_count,
            "rto_count": rto_count,
            "observed_rate": rate,
            "saturation_multiplier": _RTO_RATE_SIGNAL_MULTIPLIER,
            "confident": True,
            "rate_source": "customer_history",
        },
    )
```

- [ ] **Step 3:** Some pre-existing agent tests may have seeded `fulfillment_status` on order rows expecting the old behavior. Update those to seed shipment rows instead. The agent's `_score_order` looks up customer via `n.get("customer_source_id")` from the order being scored — the customer hash on the order's normalized payload is what the rewire reads. Verify the Shopify mapper carries `customer_source_id` on orders, hashed the same way. If not (it currently doesn't), add it: hash the order's `customer_email`/`customer_phone` in the Shopify mapper before this task closes. Otherwise the test scenarios won't compose.

- [ ] **Step 4:** Lint + full suite. Commit.

```
git commit -m "feat(rto-agent): customer_rto_rate reads Shiprocket shipments + customer_source_id on orders"
```

---

## Task 5 — Frontend: demo Enable buttons + connectors-list surfacing

**Files:** `apps/web/src/modules/connectors/api/client.ts`, `components/EnableDemoButton.tsx`, modify `ConnectorCard.tsx` (or wherever the per-connector CTA renders).

- [ ] **Step 1:** Zod schema in `api/client.ts` picks up `is_demo: z.boolean()` on the connector summary. Add `connectDemo(name: ConnectorName)` fetcher → `POST /connectors/{name}/connect-demo`.

- [ ] **Step 2:** `EnableDemoButton.tsx` — a small button that:

```tsx
export function EnableDemoButton({ name, connectorName }: Props) {
  const mutation = useConnectDemo(connectorName);
  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
      {mutation.isPending ? 'Enabling…' : 'Enable demo data'}
    </Button>
  );
}
```

`useConnectDemo` is a small TanStack Query mutation that on success: invalidates `['connectors']`, toasts "Demo data enabled for {name} — click Sync to load."

- [ ] **Step 3:** Update `ConnectorCard.tsx`. Branch on the new `is_demo` flag:
  - Not connected + `!is_demo` → existing OAuth "Connect" button (Shopify).
  - Not connected + `is_demo` → `EnableDemoButton`.
  - Connected → existing `Sync` button + `Disconnect`. Add a small "Demo" badge if `is_demo` so the UI is honest.

- [ ] **Step 4:** `pnpm typecheck && pnpm lint && pnpm build`. Commit.

```
git commit -m "feat(web): enable-demo button for Meta + Shiprocket cards + is_demo badge"
```

---

## Task 6 — Live smoke + docs + push

- [ ] **Step 1:** Start both servers (recipe from Phase 7). Walk:
  1. `/connectors` shows three cards: Shopify (Connected, real), Meta Ads (Not connected, demo badge), Shiprocket (Not connected, demo badge).
  2. Click "Enable demo data" on Meta → toast → card flips to Connected. Click Sync → records page shows ad_spend rows.
  3. Click "Enable demo data" on Shiprocket → toast → card flips to Connected. Click Sync → records page shows shipment rows; customer A has 5 with 3 RTOs.
  4. Click "Run agent now" on `/agents`. Detail sheet: customer A's order shows `rate_source: customer_history`, score saturates the customer signal; the run proposes `convert_to_prepaid` for customer A's COD orders and `no_action` for customer B's clean record.
  5. `/chat`: ask "Which campaign had the highest ROAS last week?" — response cites Meta `record_id`s via the citation badges.
  6. `/chat`: ask "Which customer has the highest RTO rate?" — response cites Shiprocket shipment rows.

- [ ] **Step 2:** `CHANGELOG.md` entry. Note: three connectors behind one abstraction, demo-mode for Meta + Shiprocket with fixture sources and honest README labeling; `customer_rto_rate` rewire is the under-the-hood improvement.

- [ ] **Step 3:** `context.md` — bump Now / Done / Next. Capture any paid lessons from the cycle.

- [ ] **Step 4:** Commit, run reviewer subagent on the diff, apply fixes, push.

```
git add CHANGELOG.md context.md
git commit -m "docs(phase-8): record Meta + Shiprocket demo connectors + RTO agent rewire"
# (then reviewer cycle, then push)
```

---

## Self-review

**Brief coverage:**
- ≥3 connectors behind one abstraction: Shopify + Meta Ads + Shiprocket, all `BaseConnector` subclasses. ✓
- Universal data model with provenance: every row carries `source_system`, `source_id`, `entity_type`, `fetched_at`, `payload_hash`, `raw`. ✓
- AI employee demo: RTO agent's `customer_rto_rate` now consumes real-shape Shiprocket shipment data through the same code path real Shiprocket would use. The fixture is the only difference, called out in README. ✓

**Type / name consistency:**
- `SourceSystem.{SHOPIFY,META_ADS,SHIPROCKET}` and `ConnectorName.{SHOPIFY,META_ADS,SHIPROCKET}` — verify exist in `shared/constants.py` (they do).
- `CredentialStatus.DEMO` — verify exists (it does).
- `FulfillmentStatus.IN_TRANSIT` — likely missing; add in Task 2.

**Test discipline (§13.4):**
- Mapper tests pin status enum coverage, IST→UTC time conversion (Phase 6 paid lesson regression-locked), customer-hash determinism, typed errors on unknown values.
- Connector tests pin end-to-end sync writes and idempotency.
- Demo-connect endpoint tests pin the three branches: success, not-demo-connector, unknown-connector.
- Agent tests pin: shipments drive the signal, non-shiprocket records ignored, baseline kicks in below threshold.

**Past lessons baked in:**
- Comment discipline (Phases 5–7): no task/phase/reviewer-referential comments, no narration.
- API contracts (Phase 7): Meta `/insights` shape and Shiprocket `/v1/external/orders` shape verified against provider docs while writing this plan.
- IST→UTC at the wire boundary (Phase 6 timezone bug): Shiprocket emits IST-naive timestamps; the mapper converts explicitly.
- Typed errors on unknown enum values (Phase 5 silent-fallback lessons): both mappers raise typed errors on unmappable inputs, never silent buckets.
- §4.3 typed error codes: `CONNECTOR_NOT_DEMO`, `CONNECTOR_UNKNOWN` (existing) — frontend branches on `code`, not `message`.

**Honest gaps documented for README:**
- Meta and Shiprocket are demo-mode. Real connectors swap in by replacing the fixture-reading `sync()` with an HTTP-calling one; abstraction is identical.
- Shiprocket has no public sandbox; demo-mode is the deliberate scope choice, not a workaround.
- `customer_source_id` hash collisions are theoretically possible (two customers with identical email AND phone). Acceptable for v0.
- The `MetaAdsConnector` and `ShiprocketConnector` share ~80% of their shape (fixture read + sink + log). §3.3 says don't extract a base until the third occurrence; resist the urge. If a fourth demo connector lands, extract `DemoConnectorBase` then.

**Risk callouts for the reviewer:**
- The Shopify mapper currently doesn't carry `customer_source_id` on order rows (`record.normalized`). Task 4 adds it. Verify the Phase 4 Shopify mapper isn't broken by the addition — adding a field to `normalized` is additive, but if any test asserts the exact shape (it shouldn't, but check), update it.
- `is_demo` is a class attribute on `BaseConnector`. The connector-list endpoint reads it via `connector_cls.is_demo`. Verify the existing `connectors/service.py` constructs from the class (not from an instance) when responding to GET.
- The fixture files live in `connectors/<name>/fixtures/`. `Path(__file__).parent / "fixtures" / "..."` works for the standard `uv run` flow. **For Phase 9 docker-compose, verify the fixture is included in the wheel/package; if hatchling doesn't pull `.json` files by default, add `include = ["**/*.json"]` to pyproject.toml's `[tool.hatch.build.targets.wheel]`.**
