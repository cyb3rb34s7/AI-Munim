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
│  │  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐   │ │
│  │  │ Connectors   │    │ Universal schema │    │ Agents               │   │ │
│  │  │ (BaseConnec- │    │ (single `record` │    │  - RTO Mitigator     │   │ │
│  │  │  tor + 3     │───▶│  table, JSON     │◀───│    (cron via         │   │ │
│  │  │  impls)      │    │  normalized +    │    │     APScheduler)     │   │ │
│  │  │              │    │  raw provenance) │    │                      │   │ │
│  │  └──────┬───────┘    └──────────┬───────┘    └──────────┬───────────┘   │ │
│  └─────────┼───────────────────────┼───────────────────────┼────────────────┘ │
│            │                       │                       │                  │
│            ▼                       ▼                       ▼                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐│
│  │            SQLite (v0)  →  Postgres path (described in §10)                ││
│  │                                                                            ││
│  │   merchant · connector_credentials · record · run_log                      ││
│  └───────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────────┘
            ▲
            │  outbound API calls (cron-driven sync)
            │
   ┌────────┴────────┐  ┌──────────────┐  ┌──────────────┐
   │ Shopify Admin   │  │ Meta Marketing│  │ Shiprocket   │
   │ API             │  │ API           │  │ API          │
   └─────────────────┘  └──────────────┘  └──────────────┘
```

Three things to notice in that diagram:

1. **The `record` table sits in the middle.** Everything flows in through connectors and out through chat tools. Chat tools never touch source APIs directly — they read from the synced `record` rows. That's how citations stay coherent and reproducible.
2. **There are only four tables.** `merchant`, `connector_credentials`, `record`, `run_log`. No per-entity tables. Universal schema means one shape (see §4).
3. **Chat and agent share the same domain layer.** Only the trigger differs: a user message versus a cron tick. Both read the same `record` rows, both write to the same `run_log`.

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
| MCP | Not in v0. Acknowledged as a viable future path. | We considered exposing our own MCP server and routing chat tools through official Shopify/Meta/Shiprocket MCPs. We chose direct connector + in-process tools for v0 to keep the integration path explicit, the latency lower, and the citation contract enforced inside our own boundary. The connector and tool layers are deliberately structured so an MCP wrapper can be added later without touching the chat layer. |
| Scheduling | **APScheduler** (in-process) | No Redis/Celery needed for v0. The cron path lifts to a queue trivially when we scale (§10). |
| HTTP client | `httpx` | Async, modern. Used by both connectors and tests (with `httpx-mock`). |
| Lint/format | `ruff` (lint + format) + `mypy` | One tool covers what black/isort/flake8 used to. Fast. |
| Testing | `pytest` + `pytest-asyncio` + VCR-style cassettes for connectors | Real-API recordings, CI-friendly replays. |

### Frontend (`apps/web`)

| Layer | Choice | Why |
|---|---|---|
| Build tool / framework | **Vite 6 + React 19** | The frontend is a single-page admin UI. No SSR, no SEO concern, no edge-runtime story to justify the Next.js footprint. Vite gives sub-second HMR and a ~700ms production build at our current size — the iteration cost on a 4-day clock matters. The original plan picked Next.js; that decision was reversed at the start of Phase 1 build (see `CHANGELOG.md` 2026-05-13). |
| Styling | **Tailwind v4** via the `@tailwindcss/vite` plugin | First-class Vite integration in v4. CSS variables (`@theme inline` + `:root` / `.dark` token blocks) drive both light and dark themes from one set of utility classes — no `dark:` sprinkling. shadcn/ui components can be dropped in later if a need surfaces; they're framework-agnostic. |
| HTTP client | **ky** | Tiny fetch wrapper with retries, hooks, and typed errors. Wrapped once in `shared/api/client.ts` to enforce the envelope unwrap + Zod boundary validation; components and hooks never see the envelope. |
| LLM streaming | **Vercel AI SDK 5** | The SDK is framework-agnostic in v5; `useChat` + Data Stream Protocol work cleanly with Vite. The "officially supported FastAPI hybrid pattern" doesn't require Next.js. |
| Charts | **Tremor** (built on Recharts) | Clean dashboards, fewer rough edges than raw Recharts. |
| State | TanStack Query (server state) + Zustand (UI state, persisted for theme) | Don't mix the two — TanStack already does cache/refetch/invalidation well. |
| Types | TypeScript end-to-end | Pydantic schemas in `apps/api/src/munim/schemas/` are the source of truth; mirrored to the frontend as Zod schemas, validated at the API client boundary so contract drift fails fast. |

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
              │    for each entity in page:     │
              │      Order(**fields)            │
              │        → .model_dump_json()     │
              │        → record row with:       │
              │            entity_type='order'  │
              │            source_system=       │
              │              'shopify'          │
              │            source_id=           │
              │              <shopify-id>       │
              │            fetched_at=now       │
              │            payload_hash=        │
              │              sha256(raw)        │
              │            raw=<verbatim>       │
              │            normalized=<order>   │
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

Every row written to the `record` table uses the natural key `(merchant_id, source_system, source_id)`. The writer upserts on that key, comparing `payload_hash` to decide whether `normalized` actually needs to be re-derived. Re-running a sync produces the same final state.

### 3.3. Provenance — raw and normalised live on the same row

Provenance is not a separate table; it is the `raw` JSON column on every `record` row. `raw` is the source's response verbatim; `normalized` is our canonical Pydantic shape. Citations resolve to `record.id`, and the UI surfaces both `raw` and `normalized` when a citation is clicked.

The single-row design means there is no foreign-key walk between "normalised data" and "source payload" — they are literally the same row.

---

## 4. Universal schema — single-table polymorphic

The data schema is **one table**, polymorphic by `entity_type`. Every connector for every source for every entity type writes rows here. Adding a new connector — or a brand-new entity type — requires **no DDL**.

This is what "universal" actually means: the *shape* is the same regardless of source or entity. Typed entity definitions live in application code (Pydantic models), not in DB tables.

### 4.1. The `record` table — universal storage

```sql
-- One row per merchant. v0 has one merchant. The merchant_id is present everywhere.
CREATE TABLE merchant (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Connector credentials. Tokens never leave this table.
CREATE TABLE connector_credentials (
    id                  INTEGER PRIMARY KEY,
    merchant_id         TEXT NOT NULL,
    connector           TEXT NOT NULL,         -- 'shopify' | 'meta_ads' | 'shiprocket' | <any>
    auth_blob_encrypted TEXT NOT NULL,         -- AES-GCM with key from env
    status              TEXT NOT NULL,         -- 'connected' | 'demo' | 'error'
    last_sync_at        DATETIME,
    UNIQUE (merchant_id, connector)
);

-- The universal identity layer. Every data record from every connector lives here.
CREATE TABLE record (
    id             INTEGER  PRIMARY KEY,
    merchant_id    TEXT     NOT NULL,
    source_system  TEXT     NOT NULL,          -- 'shopify' | 'meta_ads' | 'shiprocket' | <any>
    source_id      TEXT     NOT NULL,          -- the source's own id
    entity_type    TEXT     NOT NULL,          -- 'order' | 'shipment' | 'ad_spend' | <any>
    fetched_at     DATETIME NOT NULL,
    payload_hash   TEXT     NOT NULL,          -- sha256 of the raw payload
    raw            JSON     NOT NULL,          -- source response, verbatim (provenance)
    normalized     JSON     NOT NULL,          -- our canonical shape for this entity_type
    UNIQUE (merchant_id, source_system, source_id)
);

-- Append-only audit / observability. Used by chat, sync, and agent runs.
CREATE TABLE run_log (
    id          INTEGER  PRIMARY KEY,
    merchant_id TEXT     NOT NULL,
    kind        TEXT     NOT NULL,             -- 'sync' | 'chat' | 'agent'
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    detail_json TEXT     NOT NULL              -- full structured payload of the run
);
```

That's the entire schema. **Four tables:** `merchant`, `connector_credentials`, `record`, `run_log`. Nothing entity-specific.

### 4.2. Typed shapes live in code, not in tables

Entity definitions are Pydantic models in `apps/api/src/munim/schemas/`:

```python
class Order(BaseModel):
    placed_at: datetime
    total_inr: Decimal
    payment_method: Literal['cod', 'prepaid', 'partial']
    financial_status: str
    fulfillment_status: str | None = None
    pincode: str | None = None
    utm_campaign: str | None = None
    customer_source_id: str | None = None
    # ...

class Shipment(BaseModel):
    awb: str
    courier: str
    status: str                                # 'in_transit' | 'delivered' | 'rto' | ...
    pincode: str | None = None
    is_cod: bool
    rto_at: datetime | None = None
    delivered_at: datetime | None = None

# Same pattern for: Customer, Product, AdCampaign, AdSpend, Payment, etc.
```

A connector's mapper produces an `Order(...)` instance, serialises it with `.model_dump_json()`, and stores the result as the `normalized` JSON of a `record` row with `entity_type='order'`. Validation lives in Pydantic; storage lives in SQL.

### 4.3. Indexing — partial indexes per hot path

Indexes are an optimisation per hot query path, not part of the universal model:

```sql
-- Hot path: orders by placed_at and payment method.
CREATE INDEX ix_record_order_placed_at
    ON record (json_extract(normalized, '$.placed_at') DESC)
    WHERE entity_type = 'order';

CREATE INDEX ix_record_order_payment_method
    ON record (json_extract(normalized, '$.payment_method'))
    WHERE entity_type = 'order';

-- Hot path: shipments by status.
CREATE INDEX ix_record_shipment_status
    ON record (json_extract(normalized, '$.status'))
    WHERE entity_type = 'shipment';

-- Provenance / general lookups.
CREATE INDEX ix_record_source ON record (source_system, source_id);
CREATE INDEX ix_record_merchant_entity_time
    ON record (merchant_id, entity_type, fetched_at DESC);
```

Partial indexes on JSON expressions. SQLite supports them; Postgres `JSONB` supports them even better. **Adding an index for a newly-hot query does not change the schema.**

### 4.4. What "adding a new connector" looks like

| Scenario | Steps | DDL? |
|---|---|---|
| New source for an existing entity type (e.g., WooCommerce orders) | Implement `BaseConnector`. Mapper: WooCommerce response → existing `Order` Pydantic model → `record` row with `entity_type='order'`. | **None** |
| New source for a brand-new entity type (e.g., HubSpot deals) | Implement `BaseConnector`. Define `class Deal(BaseModel)` in code. Mapper produces `record` rows with `entity_type='deal'`. Existing chat tools are unchanged; a new tool wrapper can be added if `deal` becomes a queryable entity. | **None** |
| New payment provider alongside an existing one (e.g., Cashfree + Razorpay) | Both connectors write `record` rows with `entity_type='payment'`. They coexist; `(source_system, source_id)` uniqueness keeps them separate. | **None** |
| A query path becomes hot enough to need an index | Add a partial index on the relevant JSON path. | Index DDL only; no table changes. |

### 4.5. Why this is honestly universal

- **One table at storage.** No per-entity tables hidden behind a fancier name. Provenance is on every row by construction.
- **Schema as types, not as DDL.** The shape of an `Order` is a Pydantic class. Changing the shape changes Python, not SQL. Migrations are mostly avoided.
- **Citations resolve to one ID space.** Every `RowCitation` points at a `record.id`. No table discrimination at citation time.
- **Indexes are opt-in optimisations.** They don't constrain the model; they speed up specific queries.
- **The schema scales horizontally with `merchant_id`.** Partitioning at scale is a Postgres operation on one table, not seven.

### 4.6. Notes and constraints

- **`source_system` + `source_id` is the natural key** within a merchant. Internal `id` is for joins only; never user-visible.
- **`payload_hash`** lets us detect duplicate or updated payloads. We upsert on `(merchant_id, source_system, source_id)` and only update if the hash differs.
- **Money** is stored in `normalized` JSON as a Pydantic `Decimal` (serialised as a string by default). We cast back to `Decimal` at compute time. Floats never touch a rupee value.
- **Pincode is a string**, not an int. Leading-zero pincodes exist in some regions.
- **`raw` is the source's response verbatim.** `normalized` is our Pydantic canonical shape. The UI surfaces both when a citation is clicked.

This satisfies FR-2.1 through FR-2.5.

### 4.7. Why SQLite + JSON columns, not MongoDB

This is the natural follow-up question: the design we just described is essentially a document store on top of SQL. Why not just use a document store?

| | SQLite + JSON | MongoDB | Postgres + JSONB |
|---|---|---|---|
| Document/JSON storage | First-class `JSON` type | Native | First-class `JSONB` |
| Partial indexes on JSON paths | Yes | Yes | Yes (best of the three) |
| ACID transactions | Yes, full | Yes (since 4.0) | Yes, full |
| Query language | SQL + JSON functions | MQL + aggregation pipeline | SQL + JSON functions |
| Single-file deploy | Yes — just a file | No — needs a service | No — needs a service |
| Demo experience (`docker-compose up` → it works) | Trivial | Add service + init + health probe | Add service + init + health probe |
| Citation contract joins (`record` × `run_log` × `connector_credentials`) | Natural — these are relational | Workable but split-brain feels worse on relational metadata | Natural |
| Migration path from v0 to scale | `pg_dump` to Postgres, same SQL | Stay on Mongo or migrate (harder) | Already at scale |
| Familiarity for evaluators | High | High | Highest |

**The honest tradeoff:** MongoDB is a defensible alternative. It is document-native, mature, and well-understood. We picked SQLite + JSON columns for v0 for three concrete reasons:

1. **Demo experience matters.** A reviewer clones the repo and runs `docker-compose up`. SQLite is a file mounted into a volume — no service to provision, no init script, no readiness probe. Mongo adds non-trivial setup that buys nothing demo-relevant.
2. **The citation contract benefits from SQL-native joins.** `record` rows need to be cross-referenced with `run_log` (was this row referenced by an agent run?) and `connector_credentials` (which connector produced it?). Both are relational metadata. Keeping them in the same SQL store, in the same transaction, with the same query language, is simpler than the SQL-plus-Mongo hybrid we'd otherwise need.
3. **The Postgres upgrade path is preserved.** SQLite → Postgres is largely a configuration change because we use SQLAlchemy/SQLModel and standard `JSON` semantics. JSONB indexes, partitioning, and replication light up at scale without rewriting application code.

**When MongoDB would be the right call:** if our data shape were deeply nested with frequent free-form aggregations, if we expected to scale to TBs with horizontal sharding, or if the team's expertise was strongly Mongo-leaning. For a v0 demonstrating an agent + citation contract pattern over a few million records per merchant, SQLite + JSON columns is the leaner pick. We get 95% of MongoDB's flexibility (one polymorphic table, JSON values, indexable JSON paths) without the infra cost at v0 scale.

This is also why §4.5 calls the model "honestly universal": the universality is in the *shape*, not in the *engine*. Move from SQLite to Postgres at scale without changing the model. Move to MongoDB at much larger scale with a rewrite the cost of one sprint, not one quarter — because the application-side Pydantic models *are* the entity contract; the storage engine is replaceable.

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
    record_id: int                     # FK to record.id — the universal identity layer
    entity_type: str                   # 'order' | 'shipment' | 'ad_spend' | <any>
    source_system: str                 # 'shopify' | 'meta_ads' | 'shiprocket' | <any>
    source_id: str                     # the source's own id
    excerpt: dict[str, Any]            # the relevant field projection from normalized
```

Citations are produced by the tool, *not* the LLM. The tool knows exactly which `record` rows it touched. The LLM only sees the citations and quotes them.

Because every citation resolves to **one canonical row type** (`record`), the validator does not need per-table logic. There is one ID space, one lookup, one provenance shape.

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

The UI renders `[cite:N]` markers as inline shadcn `<Badge>` components. Clicking a badge opens a popover showing the cited `record` row's `normalized` shape, with a link to expand the `raw` source payload from the same row.

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

Tools read from the single `record` table, filtered by `entity_type` and the `normalized` JSON path expressions that match each tool's intent. The LLM never writes SQL; it composes through these tool calls.

The full set of tools exposed to the LLM:

| Tool | Args | Reads | Returns |
|---|---|---|---|
| `query_orders` | filters: date range, payment method, status, campaign, pincode | `record WHERE entity_type='order'` | rows + citations |
| `query_shipments` | filters: status, courier, pincode, date range | `record WHERE entity_type='shipment'`, joined back to orders by `source_id` when needed | rows + citations |
| `query_ad_spend` | filters: campaign, date range, granularity | `record WHERE entity_type='ad_spend'` | rows + citations |
| `query_customer_history` | customer source_id or phone hash | `record` filtered to a customer's orders + shipments | rows + citations |
| `compute_metric` | formula: enum, scope: filters | composes the above | number + citations |
| `propose_action` | action_type, target_id, reasoning, evidence_record_ids | (no read; surfaces the agent's intent) | confirmation only |

Tools are deliberately small and explicit. The LLM cannot ask for "everything"; it must compose questions.

`compute_metric` is the linchpin of the citation contract: aggregations carry the `record_id` citations of every row that contributed to the number, so any derived figure remains traceable to its source rows.

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
    │      record WHERE entity_type='order'
    │             AND normalized->>'payment_method'='cod'
    │             AND fetched_at > last_run_at
    │
    ├── For each order, gather signals (all reads against `record`):
    │     - customer_rto_rate    ← shipment records for this customer
    │     - pincode_rto_rate     ← shipment records aggregated by pincode
    │     - order_value_bucket   ← order.normalized.total_inr binned
    │     - product_category     ← order's line items → product records
    │     - time_of_order_band   ← order.normalized.placed_at hour-of-day
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
            merchant_id, kind='agent', agent='rto_mitigator',
            orders_scanned: N, actions_proposed: M,
            per_order_decisions: [
              {record_id, score, signals, action,
               estimated_inr_saved,
               cited_record_ids: [...] }
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

## 9. MCP — why it isn't in v0

This section exists to be explicit about a choice we made and didn't make. MCP (Anthropic's Model Context Protocol) has become a real distribution channel in 2026: Shopify, Stripe, Klaviyo ship official MCP servers; Meta released an official MCP server in April 2026; `bfrs/shiprocket-mcp` (by Bigfoot Retail Solutions, Shiprocket's parent) exists. A reasonable question is "why doesn't Munim use MCP?"

**We considered three possible MCP roles and rejected all of them for v0:**

| Role | What it would mean | Why not in v0 |
|---|---|---|
| Consume vendor MCPs for sync | Our connectors call Shopify/Meta/Shiprocket via MCP instead of REST | Loses control over rate limiting, retries, pagination, schema mapping. The brief asks for a connector abstraction we own; MCP is a transport, not the integration. |
| Consume vendor MCPs as chat tools | Chat agent calls Shopify/Meta MCPs live during a conversation | Side-effect surface (creates orders, schedules pickups) we explicitly avoid in v0. Citation contract becomes harder when the data isn't already in our `record` store. |
| Expose our own MCP server | `apps/api` runs an `FastMCP` server so Claude Desktop / Cursor can query Munim | Useful but orthogonal to the brief's five requirements. Adds a deployment surface and an auth model we don't need to demonstrate the chat + agent value. |

**What we did instead:** keep connectors as direct REST clients (so we own the rate-limiting, schema mapping, and provenance), keep chat tools as in-process Python functions (so the citation contract is enforced within one boundary), and structure the code so any of these MCP roles can be added later without touching the chat layer.

The acknowledgment of `bfrs/shiprocket-mcp` in §15 remains genuine — it shaped how we thought about Shiprocket integration. We deliberately did not duplicate or compete with it.

---

## 10. Scale story — 1 merchant to 10,000

The v0 runs for one merchant on SQLite. Here is what breaks first as we scale, in order, and what we did or sketched to absorb it.

### 10.1. What breaks first, ranked

| Rank | What breaks | When | Mitigation in v0 | Mitigation at scale |
|---|---|---|---|---|
| 1 | **Connector rate limits.** Shopify Admin API ~2 req/sec/store, Meta Marketing API quota-based, Shiprocket undocumented but low. | First 5–20 merchants on a shared key | Per-connector rate limit decorator on each `sync_*` call; exponential backoff with jitter | Per-merchant token buckets in Redis; tiered sync (hot/warm/cold); webhook-first where supported (Shopify), polling-only where not (Shiprocket) |
| 2 | **Sync orchestration.** Inline `await sync_full()` is fine for 1 merchant; not for 10k. | ~50–100 merchants | APScheduler in-process scheduler | Temporal or Celery workers, idempotent activities, per-merchant queue |
| 3 | **Database contention.** SQLite is fine read-heavy single-writer; not fine multi-tenant write. | ~10–50 merchants | `merchant_id` is everywhere, every query is scoped, even though there's only one merchant in v0 | Postgres with declarative partition on `record` by `merchant_id` (and sub-partition by `entity_type` if needed); read replicas for chat queries. Only one table to partition. |
| 4 | **LLM cost.** Reasoning calls per chat are bounded but agent runs accumulate. | First 100 merchants if agent fires every 30 min on a frontier model | Routing-vs-reasoning split (cheap `gpt-4o-mini` for routing, Sonnet for final synthesis); agent uses cheap model + deterministic scoring code | Cache tool results within session; per-merchant LLM budget; fall back to local small models for routing when ROI of the cloud call is low |
| 5 | **Run log growth.** Every chat, every tool call, every agent run is persisted. | ~1000 merchants × 30-day retention | Bounded retention (90 days default), aggregated counters | Move run logs to a column store (ClickHouse or DuckDB); keep last 30 days hot, archive cold |
| 6 | **Multi-tenant isolation.** v0 has no auth. | Day 1 of paying customers | Single-tenant deployment, key-based isolation in fixtures | Per-merchant Postgres schema or row-level security; per-merchant encryption keys for `connector_credentials.auth_blob_encrypted` |
| 7 | **Citation verification cost.** Every response is post-processed; every claim resolved. | ~50,000 chats/day | Linear scan over `text` is cheap (~ms) | Same approach scales; nothing to do |

### 10.2. What we built in v0 to absorb the future

These design choices cost us no time today but unlock the scale-out:

- **`merchant_id` on every row** even though there is one merchant
- **Single-table polymorphic schema** — partition by `merchant_id` on one table instead of seven
- **Connector classes are stateless objects** — they accept context, return rows. Trivially parallelised.
- **`SyncContext`/`RowSink` abstraction** — switching from inline write to a queue is one class
- **`run_log` is append-only** — easy to ship to a column store later
- **PydanticAI provider abstraction** — switching models doesn't touch tool definitions
- **Connector + tool layers are MCP-ready** — adding an MCP wrapper later does not change the chat or schema

### 10.3. What we sketched but did not build

- A `load_test.py` script that fans out N concurrent fake-merchant sync runs and measures throughput.
- A Postgres migration plan: `alembic` baseline already in the project (no migrations needed yet, but the harness is there).
- A Redis-backed rate limiter (the interface exists in `connectors.rate_limit`; the in-memory and Redis implementations both implement the same interface; we ship the in-memory one).

This satisfies FR-5.1, FR-5.2, FR-5.3.

---

## 11. Security model

- **Secrets in env, not in code.** `.env` is git-ignored. `.env.example` is committed with empty values.
- **OAuth tokens encrypted at rest.** `connector_credentials.auth_blob_encrypted` uses AES-GCM with a key sourced from env. Decryption only happens inside the connector layer; tokens never reach the chat tool layer.
- **The LLM never sees credentials.** Tool inputs and outputs are scoped projections of the `normalized` JSON shape; no token, no API key, no PII-bearing field unless explicitly required.
- **PII isolation.** The `raw` JSON column on `record` may contain phone numbers and addresses; it is local-only and never sent to the LLM. The chat layer only sees the `normalized` projection unless a tool explicitly extracts a `raw` field.
- **Demo mode without keys.** A reviewer who clones the repo with no API keys gets a fixture-backed experience, not a credential error.
- **Citations expose `record.id`, not `raw` payloads.** Clicking a citation in the UI loads the row's `normalized` shape; the `raw` payload is shown only on explicit drill-in.

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
- `web` → any static host (Vercel, Netlify, Cloudflare Pages) — the Vite build produces a plain `dist/` directory with `index.html` + bundled assets.
- Sync workers → separate process group, same image, different command (`python -m munim.workers.sync`).
- (Optional, not in v0) MCP wrapper → mount `FastMCP` on a distinct route exposing the same in-process tools, so external MCP clients can query the unified data.

---

## 14. What is conspicuously missing in v0

These are not bugs; they are scoping decisions called out in the open:

- **No real OAuth for Meta or Shiprocket** — they go through a mock OAuth flow with the same UI as the real Shopify OAuth. The `BaseConnector` interface is identical; flipping to real is a connector-internal change.
- **No paraphrase verification of citations.** Numeric-exact comparison against citation rows is listed as a known gap (§5.5).
- **No MCP layer.** Neither consuming vendor MCPs nor exposing our own — see §9 for the reasoning and a future-work sketch.
- **No user authentication or SSO.** Single-user demo.
- **No webhook ingestion.** Polling-only sync via APScheduler.
- **No GraphQL / no batched chat endpoints.** REST + streaming SSE only.
- **No analytics caching layer.** Every chat query re-runs over `record`. Acceptable at v0 scale; called out as the next bottleneck in §10.

Each of these has a one-paragraph upgrade path in the README's "what we'd do with another week" section.

---

## 15. Inspirations and acknowledgments

- Architecture patterns: **NousResearch/hermes-agent** — specifically the cron-as-first-class-data-flow, the tool registry, and the platform-agnostic core principle.
- Generative UI shape: **Google A2UI v0.9** — typed render specs flowing from tool to renderer.
- Streaming UX: **Vercel AI SDK + FastAPI** — using their officially supported hybrid pattern. The SDK is framework-agnostic in v5, so it pairs equally well with Vite-hosted React as it would with Next.js.
- Schema shape: **MongoDB and event-sourcing literature** — the single-table polymorphic model with typed application-side schemas is a recognisably document-store-shaped design, executed on SQL.
- Shiprocket integration awareness: **bfrs/shiprocket-mcp** — by Bigfoot Retail Solutions (Shiprocket's parent). We deliberately did not duplicate or compete with it; see §9.
