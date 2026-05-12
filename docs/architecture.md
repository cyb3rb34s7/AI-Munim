# Architecture

> The technical deep-dive. Read this if you want to know exactly what we built, how the citation contract is enforced, what the agent actually does, and what breaks first at scale.

If you have not read [`requirements.md`](requirements.md) yet, do that first — this document references those FRs and NFRs by id.

---

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              apps/web  (Next.js)                              │
│                                                                                │
│   ┌────────────────────────┐    ┌────────────────────────┐                     │
│   │ /chat                  │    │ /settings/connectors   │                     │
│   │   - useChat (AI SDK)   │    │   - Connector cards    │                     │
│   │   - Streams answer     │    │   - One-click OAuth    │                     │
│   │   - Inline artifacts   │    │   - Sync status        │                     │
│   │   - Citation badges    │    │                        │                     │
│   └───────────┬────────────┘    └────────────┬───────────┘                     │
│               │                              │                                 │
│               │  Data Stream Protocol        │  REST                           │
└───────────────┼──────────────────────────────┼─────────────────────────────────┘
                │                              │
                ▼                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          apps/api  (FastAPI, Python)                          │
│                                                                                │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────┐   │
│  │ /api/chat          │  │ /api/connectors    │  │ /api/agent/runs        │   │
│  │  - PydanticAI loop │  │  - OAuth init/cb   │  │  - List run logs       │   │
│  │  - Tools registry  │  │  - Trigger sync    │  │  - Trigger one-off     │   │
│  │  - Citation        │  │  - Status          │  │                        │   │
│  │    enforcer        │  │                    │  │                        │   │
│  └─────────┬──────────┘  └─────────┬──────────┘  └────────────┬───────────┘   │
│            │                       │                          │                │
│            ▼                       ▼                          ▼                │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                        Domain layer                                       │ │
│  │                                                                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐ │ │
│  │  │ Connectors  │  │ Universal   │  │ MCP server  │  │ Agents           │ │ │
│  │  │ (Base +     │  │ schema +    │  │ (FastMCP)   │  │ - RTO Mitigator  │ │ │
│  │  │ 3 impls)    │  │ provenance  │  │             │  │  (cron via       │ │ │
│  │  │             │  │             │  │ Exposes our │  │   APScheduler)   │ │ │
│  │  │             │  │             │  │ unified data│  │                  │ │ │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └────────┬─────────┘ │ │
│  └─────────┼────────────────┼─────────────────────────────────────┼─────────┘ │
│            │                │                                     │           │
│            ▼                ▼                                     ▼           │
│  ┌───────────────────────────────────────────────────────────────────────────┐│
│  │            SQLite (v0)  →  Postgres path (described in §10)                ││
│  │                                                                            ││
│  │   normalised rows · raw_payload (provenance) · run_log · creds            ││
│  └───────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────────┘
            ▲                                                  ▲
            │                                                  │
            │  outbound API calls                              │  inbound chat tool calls
            │                                                  │
   ┌────────┴────────┐  ┌──────────────┐  ┌─────────────┐     │
   │ Shopify Admin   │  │ Meta Marketing│  │ Shiprocket  │     │  Also routable through
   │ API             │  │ API           │  │ API         │     │  official MCPs for
   │ (+ Shopify MCP) │  │ (+ Meta MCP)  │  │ (+ bfrs MCP)│ ────┘  live operations.
   └─────────────────┘  └──────────────┘  └─────────────┘
```

Three things to notice in that diagram:

1. **The universal schema sits in the middle.** Everything flows in through connectors and out through tools. Tools never touch source APIs directly during chat — they read from the normalised store. That's how citations stay coherent.
2. **MCPs are an *additional* surface, not the primary integration path.** Our connectors do the data sync. Our MCP server *exposes* the unified data so any MCP client (Claude Desktop, Cursor) can query us. The official Shopify/Meta/Shiprocket MCPs are wired in as optional tools when a live action is needed.
3. **Chat and agent share the same domain layer.** Only the trigger differs: a user message versus a cron tick.

---

## 2. Tech stack with reasoning per layer

### Backend (`apps/api`)

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| Language | Python 3.11+ | Where the LLM/agent ecosystem is most mature in 2026. PydanticAI, MCP SDK, structured outputs all land cleanly. |
| Web framework | **FastAPI** | Async, native Pydantic, easy SSE/streaming, recognisable. Flask is older; Litestar is younger. FastAPI is the right balance. |
| Schema | **Pydantic + SQLModel** | Pydantic *is* the validation layer behind the OpenAI/Anthropic SDKs. SQLModel gives us an ORM that speaks Pydantic. One mental model from JSON to DB. |
| DB | **SQLite** in v0, with a documented path to Postgres | Zero setup; a reviewer can clone and run. The Postgres migration is configuration, not a rewrite (see §10). |
| Agent framework | **PydanticAI** | Provider-agnostic from day one (OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, Ollama). Typed tool definitions. Native MCP support. Why not LangGraph: too much LangChain ecosystem. Why not OpenAI Agents SDK: OpenAI-biased. Why not Hermes: generalist, too much surface area. |
| LLM providers | OpenAI `gpt-4o-mini` for routing/cheap calls; Anthropic Claude Sonnet for reasoning. **Behind an abstraction** so swapping is one config line. | Two providers, two strengths, no lock-in. |
| MCP | `mcp` (official Python SDK) + `FastMCP` for the server we expose | Industry-standard protocol. We consume Shopify/Meta/Shiprocket MCPs and expose our own. |
| Scheduling | **APScheduler** (in-process) | No Redis/Celery needed for v0. The cron path lifts to a queue trivially when we scale (§10). |
| HTTP client | `httpx` | Async, modern. Used by both connectors and tests (with `httpx-mock`). |
| Lint/format | `ruff` (lint + format) + `mypy` | One tool covers what black/isort/flake8 used to. Fast. |
| Testing | `pytest` + `pytest-asyncio` + VCR-style cassettes for connectors | Real-API recordings, CI-friendly replays. |

### Frontend (`apps/web`)

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15** (App Router) | The most recognisable React framework in 2026. Plays nicely with Vercel AI SDK. |
| Styling | **Tailwind v4 + shadcn/ui** | Industry-standard polished UI with minimal custom CSS. shadcn components are copied in, not imported, so they're ours to modify. |
| LLM streaming | **Vercel AI SDK 5** | `useChat` for the conversation, Data Stream Protocol for bridging to our Python backend. Officially supported by Vercel. |
| Charts | **Tremor** (built on Recharts) | shadcn-styled, AI-native dashboards, fewer rough edges than raw Recharts. |
| State | TanStack Query for server state, Zustand for UI state | Standard, lean. |
| Types | TypeScript end-to-end | Pydantic schemas mirrored as Zod schemas in `packages/shared-types`. Codegen path documented. |

### Shared

| Layer | Choice |
|---|---|
| Monorepo | pnpm workspaces (TS) + `uv` (Python) inside a single git repo |
| Container | `docker-compose.yml` with `api` and `web` services |
| CI | GitHub Actions: lint, typecheck, tests on every push |

---

## 3. Data flow #1 — connector sync

```
                  ┌───────────────────────┐
                  │ User clicks "Connect" │
                  └───────────┬───────────┘
                              ▼
              POST /api/connectors/shopify/oauth/init
                              │
                              ▼
              ┌─────────────────────────────────┐
              │ ShopifyConnector.authorize_url()│
              │   builds the OAuth URL          │
              └────────────────┬────────────────┘
                               ▼
                         user authorizes
                               │
                               ▼
              GET /api/connectors/shopify/oauth/callback?code=...
                               │
                               ▼
              ┌─────────────────────────────────┐
              │ ShopifyConnector.exchange_code()│
              │   → stores token in             │
              │     connector_credentials       │
              └────────────────┬────────────────┘
                               ▼
                  POST /api/connectors/shopify/sync
                               │
                               ▼
              ┌─────────────────────────────────┐
              │ ShopifyConnector.sync_full()    │
              │                                  │
              │  for each page of Shopify API:  │
              │    raw → raw_payload table      │
              │    raw → normalize() → orders   │
              │             customers           │
              │             products            │
              │    stamp every row with         │
              │      source_system='shopify'    │
              │      source_id=<shopify-id>     │
              │      fetched_at=now             │
              │      payload_hash=sha256(raw)   │
              └─────────────────────────────────┘
```

### 3.1. `BaseConnector` interface

Every connector implements:

```python
class BaseConnector(ABC):
    name: ClassVar[str]            # 'shopify', 'meta_ads', 'shiprocket'

    @abstractmethod
    def authorize_url(self, merchant_id: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, merchant_id: str, code: str) -> Credential: ...

    @abstractmethod
    async def validate(self, cred: Credential) -> bool: ...

    @abstractmethod
    async def sync_full(self, ctx: SyncContext) -> SyncResult: ...

    @abstractmethod
    async def sync_incremental(self, ctx: SyncContext) -> SyncResult: ...
```

`SyncContext` carries the merchant id, the credential, an http client, a checkpoint cursor (for incremental), and a `RowSink` writer. `RowSink` is the only way connectors write rows — it stamps provenance automatically.

This satisfies FR-1.1 through FR-1.5 directly.

### 3.2. Idempotency

Every row written to a normalised table uses the natural key `(source_system, source_id)`. The writer upserts on that key. Re-running a sync produces the same final state.

### 3.3. Raw payload preservation

The full source response is stored verbatim in `raw_payload`:

```sql
CREATE TABLE raw_payload (
    id INTEGER PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fetched_at DATETIME NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE (merchant_id, source_system, source_id, payload_hash)
);
```

Citations resolve to rows in *normalised* tables, but every normalised row has a foreign-key path to the raw payload that produced it. Clicking a citation in the UI walks this path and shows the original source response.

---

## 4. Universal schema

The canonical shape, source-agnostic, all carrying provenance.

```sql
-- One row per merchant. v0 has one merchant. The merchant_id is present everywhere.
CREATE TABLE merchant (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Connectors, OAuth/API key state. Tokens never leave this table.
CREATE TABLE connector_credentials (
    id INTEGER PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    connector TEXT NOT NULL,           -- 'shopify' | 'meta_ads' | 'shiprocket'
    auth_blob_encrypted TEXT NOT NULL, -- AES-GCM with key from env
    status TEXT NOT NULL,              -- 'connected' | 'demo' | 'error'
    last_sync_at DATETIME,
    UNIQUE (merchant_id, connector)
);

-- Source-agnostic order.
CREATE TABLE "order" (
    id INTEGER PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fetched_at DATETIME NOT NULL,
    payload_hash TEXT NOT NULL,

    order_number TEXT NOT NULL,
    placed_at DATETIME NOT NULL,
    total_inr DECIMAL(12, 2) NOT NULL,
    subtotal_inr DECIMAL(12, 2) NOT NULL,
    tax_inr DECIMAL(12, 2) NOT NULL,
    shipping_inr DECIMAL(12, 2) NOT NULL,
    payment_method TEXT NOT NULL,       -- 'cod' | 'prepaid' | 'partial'
    financial_status TEXT NOT NULL,     -- 'paid' | 'pending' | 'refunded' | ...
    fulfillment_status TEXT,            -- 'delivered' | 'rto' | 'in_transit' | ...
    customer_source_id TEXT,            -- FK lookup into customer.source_id
    pincode TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,

    UNIQUE (merchant_id, source_system, source_id)
);

-- Same provenance pattern for: order_item, customer, product,
-- shipment, ad_campaign, ad_spend_daily, payment.
```

Notes:

- **`source_system` + `source_id` is the natural key.** Internal auto-increment `id` is for joins only; never user-visible.
- **`payload_hash` lets us detect changes.** If a Shopify webhook fires twice with identical payload, we deduplicate by hash.
- **Money is `DECIMAL(12, 2)` in INR.** Floats are forbidden. (Yes, even for percentages — those are also DECIMAL.)
- **Pincode is a string, not an int.** Leading-zero pincodes exist in some regions.
- **Provenance is row-level, not table-level.** Two connectors can write into the same logical entity (e.g. Meta's UTM data enriching a Shopify order) without losing track of who said what.

This satisfies FR-2.1 through FR-2.5.

---

## 5. Citation contract — the hardest piece

This is what stops the LLM from quietly hallucinating a number. The contract has four layers, all of which must hold or the answer doesn't ship.

### 5.1. Tool return shape

Every chat tool returns this exact shape:

```python
class ToolResult(BaseModel):
    data: Any                          # whatever the tool computed
    citations: list[RowCitation]       # provenance rows that produced the data
    render: RenderSpec | None = None   # optional A2UI-shaped render hint

class RowCitation(BaseModel):
    table: str                         # 'order' | 'ad_spend_daily' | ...
    row_id: int                        # the internal id
    source_system: str
    source_id: str
    excerpt: dict[str, Any]            # the relevant field projection
```

Citations are produced by the tool, *not* the LLM. The tool knows exactly which rows it touched. The LLM only sees them and quotes them.

### 5.2. System prompt contract

The chat system prompt tells the model, in plain language:

> Every numeric value in your final answer must be wrapped as `<value>[cite:row_id,row_id,...]`. Row ids are taken from the citations returned by tools you call. If you do not have a citation for a number, do not state the number. Use `[unknown]` instead.

### 5.3. Structured output enforcement

PydanticAI lets us declare the final response type:

```python
class GroundedAnswer(BaseModel):
    text: str                          # the answer, with [cite:...] inline markers
    used_citations: list[int]          # row_ids actually referenced

answer: GroundedAnswer = await agent.run(user_message, output_type=GroundedAnswer)
```

The LLM is forced into this shape. We then validate that every `[cite:N]` in `text` references a row id that the agent's tool calls actually returned. Hallucinated row ids fail validation.

### 5.4. Fail-closed post-processor

After the structured output is validated, a final pass runs over `text`:

- Each number is required to be inside a `[cite:...]` marker.
- A regex-based scanner finds any free-floating numeric literal and replaces it with `[unverified number removed]`.
- The scanner is fail-closed: if it errors, the response is rejected and we ask the model to retry. We never ship an unverified number on the assumption that the regex was right.

The UI renders `[cite:N]` markers as inline shadcn `<Badge>` components. Clicking a badge opens a popover with the rows from `citations` and a link to the raw payload row.

This satisfies FR-3.3 through FR-3.5.

### 5.5. What this prevents and what it doesn't

| Failure mode | Prevented by | Caught by |
|---|---|---|
| Model invents a number | System prompt + structured output | Post-processor strips it |
| Model cites a fake row id | Validation | Forced retry |
| Tool returns wrong data but model trusts it | — | We log every tool call; humans can audit. The contract is correctness of provenance, not correctness of underlying data. |
| Model paraphrases a citation incorrectly (e.g. "₹12 lakh" instead of "₹12,000") | — | Not yet caught. Mitigation: planned numeric-exact comparison against citation rows. Listed as a known gap. |

Honesty: layer 4 (paraphrase verification) is not implemented in v0. It is in the README's "where it breaks" section.

---

## 6. Chat tool schema

The full set of tools exposed to the LLM:

| Tool | Args | Returns | Notes |
|---|---|---|---|
| `query_orders` | filters: date range, payment method, status, campaign, pincode | rows + citations | Read-only over normalised `order` table. |
| `query_shipments` | filters: status, courier, pincode, date range | rows + citations | Joins to `order`. |
| `query_ad_spend` | filters: campaign, date range, granularity | rows + citations | Read-only over `ad_spend_daily`. |
| `query_customer_history` | customer source_id or phone hash | rows + citations | Aggregates `order` + `shipment` for one customer. |
| `compute_metric` | formula: enum, scope: filters | number + citations | The only tool that *produces* numbers; it carries forward the citations from the rows it summed/averaged. |
| `propose_action` | action_type, target_id, reasoning, evidence_rows | confirmation only | The action is logged, not executed. Used by the chat to surface what the agent would do. |

Tools are deliberately small and explicit. The LLM cannot ask for "everything"; it must compose questions.

`compute_metric` is the linchpin of the citation contract. Aggregations carry citations across rows, so any number derived in the chat layer remains traceable.

---

## 7. Data flow #2 — chat with citations

```
User: "Which Meta campaigns are profitable after RTO losses for May?"

  → /api/chat (POST, streaming)
    → PydanticAI agent loop with tools registered
      → tool: query_ad_spend(campaign='*', date=May)         → rows + citations
      → tool: query_orders(date=May, source=meta)             → rows + citations
      → tool: query_shipments(date=May)                       → rows + citations  
      → tool: compute_metric(formula='roas_after_rto',
                              scope={campaign, date=May})     → number + citations

    → Model produces: GroundedAnswer(text="...", used_citations=[...])

    → Validator checks every [cite:N] resolves to a real citation row
       ✗ if not → retry once
       ✗ on retry fail → return error to user

    → Post-processor strips any uncited number → text'

    → Stream text' to UI via Data Stream Protocol
       UI renders streaming text, citation badges, and any
       render spec returned by tools (table, bar chart, etc.)
```

Latency budget:

- Tools execute in parallel where possible (`asyncio.gather`).
- The reasoning model (Claude Sonnet) is used for final synthesis only. Routing and tool selection use `gpt-4o-mini` for cost.
- First token in ≤ 2.5s p50 (NFR-1.1).

---

## 8. Data flow #3 — autonomous agent (RTO Risk Mitigator)

```
APScheduler tick (every 30 min, configurable)
    │
    ▼
RTOMitigatorAgent.run(merchant_id)
    │
    ├── Load new COD orders since previous run
    │      (from universal schema, single merchant scope)
    │
    ├── For each order, gather signals:
    │     - customer_rto_rate    ← join order × shipment by customer_source_id
    │     - pincode_rto_rate     ← aggregated from shipment table for pincode
    │     - order_value_bucket   ← order.total_inr binned
    │     - product_category     ← from order_item → product
    │     - time_of_order_band   ← order.placed_at hour-of-day
    │
    ├── Score = w1*customer + w2*pincode + w3*value + w4*category + w5*time
    │     (weights configurable; default in code; logged with every run)
    │
    ├── Decision tree:
    │     score > 0.6  → action = 'convert_to_prepaid'
    │     score > 0.4  → action = 'confirmation_call'
    │     else         → action = 'no_action'
    │
    ├── For each non-no-op action, compute estimated_inr_saved:
    │     = customer_rto_rate * mean_rto_cost
    │
    └── Write to run_log:
          {
            run_id, started_at, finished_at,
            merchant_id, agent='rto_mitigator',
            orders_scanned: N, actions_proposed: M,
            per_order_decisions: [
              {order_id, score, signals, action, estimated_inr_saved,
               cited_rows: [...] }
            ]
          }
        Side effects: NONE.
```

### 8.1. Why this design

- **Cron, not always-on.** Matches Hermes Agent's first-class cron flow and matches how real production agents run.
- **Signals are named and weighted explicitly.** The run log shows exactly why a decision was made.
- **Same domain layer as chat.** The agent uses the same `query_*` tools as the chat. A reviewer can ask the chat *"why did the agent flag order #12345?"* and get the same data the agent saw.
- **Cited rows are persisted in the run log.** Provenance applies to agent decisions, not just chat answers.
- **No side effects.** The agent writes proposed actions; it does not call WhatsApp, does not call Shiprocket, does not modify orders. This matches FR-4.5 and the brief.

### 8.2. Failure modes — listed before anyone asks

| Failure mode | Why it happens | Mitigation in v0 |
|---|---|---|
| False positives → harass good customers | Low data on new customers / sparse pincode stats | Threshold tuning per merchant; show false-positive rate in run log |
| Data sparsity → over-confident scores | New merchants have few historical shipments | When customer history < 3 orders, fall back to pincode + order-value signals only and lower the maximum achievable score |
| Pincode bias | Some pincodes have structural delivery issues; the agent over-recommends prepaid there | Annotate output: "score driven by pincode" so the operator sees the cause |
| Drift over time | Festive seasons spike RTO; weights become stale | Re-train cadence documented; v0 ships fixed weights with a configuration knob |
| Operator wants to override | The agent must be ignorable | The run log is read-only; nothing actually happens unless a human acts |

### 8.3. Why RTO and not something else

See [`research.md` §7](research.md). Short version: RTO is the largest single bleeding source for an Indian D2C brand at this scale, and it uniquely requires cross-tool data from Shopify and Shiprocket — proving the universal schema is worth the work.

---

## 9. MCP layers

We touch MCP in three distinct ways. They serve different jobs and shouldn't be confused.

### 9.1. We *consume* official MCPs (optional)

For live actions that don't need to flow through our universal schema, the chat agent can call out to the source's official MCP server:

- Shopify Storefront MCP, Shopify Dev MCP
- Meta Ads MCP (official, April 2026)
- `bfrs/shiprocket-mcp` (official Shiprocket MCP, by Bigfoot Retail Solutions, Shiprocket's parent)

Use cases: *"Create a new draft order for this customer"*, *"Schedule a Shiprocket pickup for these IDs"*. These are not present in v0's tool schema because they have side effects; they are wired up as gated tools available behind a feature flag.

### 9.2. Our connectors *do not need* MCPs to work

Sync goes through direct REST API calls. Connectors map raw responses into the universal schema with provenance. MCPs are not the primary integration path; they're chat surfaces.

### 9.3. We *expose* our unified data as an MCP server

Using `FastMCP`, `apps/api` runs an MCP server on a separate port that exposes the same `query_*` tools as the chat. Any MCP client (Claude Desktop, Cursor, an A2A agent) can connect and query across Shopify, Meta, and Shiprocket data with citations. This is something none of the three vendor MCPs can do — they each only see their own data.

This is the unique value-add: the merchant's data, unified, cited, queryable from any AI surface.

---

## 10. Scale story — 1 merchant to 10,000

The v0 runs for one merchant on SQLite. Here is what breaks first as we scale, in order, and what we did or sketched to absorb it.

### 10.1. What breaks first, ranked

| Rank | What breaks | When | Mitigation in v0 | Mitigation at scale |
|---|---|---|---|---|
| 1 | **Connector rate limits.** Shopify Admin API ~2 req/sec/store, Meta Marketing API quota-based, Shiprocket undocumented but low. | First 5–20 merchants on a shared key | Per-connector rate limit decorator on each `sync_*` call; exponential backoff with jitter | Per-merchant token buckets in Redis; tiered sync (hot/warm/cold); webhook-first where supported (Shopify), polling-only where not (Shiprocket) |
| 2 | **Sync orchestration.** Inline `await sync_full()` is fine for 1 merchant; not for 10k. | ~50–100 merchants | APScheduler in-process scheduler | Temporal or Celery workers, idempotent activities, per-merchant queue |
| 3 | **Database contention.** SQLite is fine read-heavy single-writer; not fine multi-tenant write. | ~10–50 merchants | `merchant_id` is everywhere, every query is scoped, even though there's only one merchant in v0 | Postgres with partition-by-merchant_id on the hot tables (`order`, `shipment`, `raw_payload`); read replicas for chat queries |
| 4 | **LLM cost.** Reasoning calls per chat are bounded but agent runs accumulate. | First 100 merchants if agent fires every 30 min on a frontier model | Routing-vs-reasoning split (cheap `gpt-4o-mini` for routing, Sonnet for final synthesis); agent uses cheap model + deterministic scoring code | Cache tool results within session; per-merchant LLM budget; fall back to local small models for routing when ROI of the cloud call is low |
| 5 | **Run log growth.** Every chat, every tool call, every agent run is persisted. | ~1000 merchants × 30-day retention | Bounded retention (90 days default), aggregated counters | Move run logs to a column store (ClickHouse or DuckDB); keep last 30 days hot, archive cold |
| 6 | **Multi-tenant isolation.** v0 has no auth. | Day 1 of paying customers | Single-tenant deployment, key-based isolation in fixtures | Per-merchant Postgres schema or row-level security; per-merchant encryption keys for `connector_credentials.auth_blob_encrypted` |
| 7 | **Citation verification cost.** Every response is post-processed; every claim resolved. | ~50,000 chats/day | Linear scan over `text` is cheap (~ms) | Same approach scales; nothing to do |

### 10.2. What we built in v0 to absorb the future

These design choices cost us no time today but unlock the scale-out:

- **`merchant_id` in every primary key** even though there is one merchant
- **Connector classes are stateless objects** — they accept context, return rows. Trivially parallelised.
- **`SyncContext`/`RowSink` abstraction** — switching from inline write to a queue is one class
- **`run_log` is append-only** — easy to ship to a column store later
- **PydanticAI provider abstraction** — switching models doesn't touch tool definitions
- **MCP server already separated** from the chat API — different scaling needs, different deployments

### 10.3. What we sketched but did not build

- A `load_test.py` script that fans out N concurrent fake-merchant sync runs and measures throughput.
- A Postgres migration plan: `alembic` baseline already in the project (no migrations needed yet, but the harness is there).
- A Redis-backed rate limiter (the interface exists in `connectors.rate_limit`; the in-memory and Redis implementations both implement the same interface; we ship the in-memory one).

This satisfies FR-5.1, FR-5.2, FR-5.3.

---

## 11. Security model

- **Secrets in env, not in code.** `.env` is git-ignored. `.env.example` is committed with empty values.
- **OAuth tokens encrypted at rest.** `connector_credentials.auth_blob_encrypted` uses AES-GCM with a key sourced from env. Decryption only happens inside the connector layer; tokens never reach the chat tool layer.
- **The LLM never sees credentials.** Tool inputs and outputs are scoped projections of normalised rows; no token, no API key, no PII-bearing field unless explicitly required.
- **PII isolation.** `raw_payload` may contain phone numbers and addresses; it is local-only and never sent to the LLM. The chat layer only sees the normalised projection.
- **Demo mode without keys.** A reviewer who clones the repo with no API keys gets a fixture-backed experience, not a credential error.
- **Citations expose row ids, not raw payloads.** Clicking a citation walks a controlled join to show the originating row in the UI; the raw payload is shown only on explicit drill-in.

---

## 12. Testing strategy

| Test type | What it covers | How |
|---|---|---|
| Unit | Connector mappers (raw → normalised); citation enforcer; scoring functions | `pytest`, frozen fixture payloads |
| Integration | Each connector's `sync_full` against recorded API responses | `pytest` + VCR-style cassettes; CI runs offline |
| Contract | Tool return shape; `GroundedAnswer` validation | Pydantic schema checks |
| Smoke / e2e | One chat round-trip end-to-end against a seeded SQLite | `pytest` calling the FastAPI app with `TestClient` |
| Agent | One RTO run against fixture orders; assert run_log shape and that no side effect was taken | `pytest` with `mock` on any HTTP call |

CI: GitHub Actions runs `ruff`, `mypy`, `pytest` on every push to `main` and on PRs.

---

## 13. Deployment plan

v0:

- `docker-compose up` runs `api` (Python/FastAPI) and `web` (Next.js).
- A volume mount persists `data/munim.sqlite` across restarts.
- A seed script populates fixtures so the demo works without any API keys.

Going beyond v0:

- `api` → containerised on Render/Railway/Fly with managed Postgres.
- `web` → Vercel.
- Sync workers → separate process group, same image, different command (`python -m munim.workers.sync`).
- MCP server → separate process group on a distinct port; doesn't share state with the API.

---

## 14. What is conspicuously missing in v0

These are not bugs; they are scoping decisions called out in the open:

- No real OAuth for Meta or Shiprocket — they go through a mock OAuth flow with the same UI as the real Shopify OAuth. The interface is identical; flipping to real is a connector-level change.
- No paraphrase verification of citations (see §5.5).
- No user authentication or SSO. Single-user demo.
- No webhook ingestion. Polling-only.
- No GraphQL / no batched chat endpoints. REST + streaming SSE only.
- No analytics caching layer. Every chat query re-runs over the normalised store.

Each of these has a one-paragraph upgrade path in the README's "what we'd do with another week" section.

---

## 15. Inspirations and acknowledgments

- Architecture patterns: **NousResearch/hermes-agent** — specifically the cron-as-first-class-data-flow, the tool registry, and the platform-agnostic core principle.
- Generative UI shape: **Google A2UI v0.9** — typed render specs flowing from tool to renderer.
- Streaming UX: **Vercel AI SDK + FastAPI** — using their officially supported hybrid pattern.
- Shiprocket integration awareness: **bfrs/shiprocket-mcp** — used as an optional live-action surface; not duplicated.
