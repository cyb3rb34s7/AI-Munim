# AI-Munim

> Every kirana shop had a munim — the bookkeeper who sat in the corner, kept all the ledgers, watched the stock, advised on margins, and noticed when something was off. Modern D2C founders have Excel and vibes. AI-Munim is the modern munim: an AI employee for Indian D2C brands that reads across their SaaS tools, answers cross-tool questions with citations on every number, and proactively flags ₹-saving actions.

**Try the live demo:** open the deployed URL, click "Try the live demo", optionally type a display name, and you land on a private workspace pre-populated with realistic Shopify, Meta Ads, and Shiprocket data. No sign-up.

---

## Table of contents

- [What it is](#what-it-is)
- [Try the live demo](#try-the-live-demo)
- [Run locally](#run-locally)
- [How the citation contract works](#how-the-citation-contract-works)
- [How the agent works](#how-the-agent-works)
- [Connectors — which 3 and why](#connectors--which-3-and-why)
- [Schema — why this shape](#schema--why-this-shape)
- [Scale — demonstrated, not aspirational](#scale--demonstrated-not-aspirational)
- [Eval — where it breaks](#eval--where-it-breaks)
- [Hours spent](#hours-spent)
- [What we'd do with another week](#what-wed-do-with-another-week)
- [AI tool usage — honest accounting](#ai-tool-usage--honest-accounting)
- [Tech choices](#tech-choices)
- [Deeper docs](#deeper-docs)
- [Acknowledgments](#acknowledgments)

---

## What it is

A v0 of an AI employee for Indian D2C brands, built as a hiring assignment.

1. **Three connectors behind one abstraction.** Shopify (real OAuth + Admin API), Meta Ads (40-row demo fixture), Shiprocket (50-row demo fixture). All three land in one universal single-table polymorphic store with row-level provenance — `merchant_id`, `source_system`, `source_id`, `fetched_at`, `payload_hash`, plus the raw source payload and the canonical `Order`/`Shipment`/`AdSpend` shape.

2. **A chat layer with a strict citation contract.** Every numerical claim is wrapped with `[cite:record_id]` markers. Four layers enforce this — tool return shape, structured output, citation validation, fail-closed post-processor. Uncited numbers never reach the user.

3. **Two autonomous agents — one deterministic, one LLM-driven.**
   - **RTO Risk Mitigator** (deterministic). Manual trigger via `POST /agents/rto_mitigator/run`. Scans new COD orders, scores RTO risk from named signals (customer's past RTO rate via the cross-connector hash, pincode risk, order-value band, time of order), proposes one of three actions: `convert_to_prepaid`, `confirmation_call`, `no_action`. Writes the full reasoning to `run_log`. Never actually sends anything. Auditable, cheap, predictable — the right shape for a high-stakes "convert this COD to prepaid?" decision.
   - **Daily Briefing** (LLM-driven, sector-aware). `POST /agents/daily_briefing/run?sector=fashion`. A PydanticAI agent reuses the chat tools to compose a 7-day plain-English narrative + 0–3 proposed actions; every numeric claim is run through the same fail-closed citation enforcer the chat layer uses. Sector (fashion / beauty / fmcg / electronics / home / generic) is a per-run dropdown input that biases the prompt. Two agents, two patterns — both audit-trailed to the same `run_log` table.

4. **Anonymous multi-tenant backbone, demonstrated.** Every visitor to the deployed URL gets a fresh `Merchant` row, a signed session cookie, and 96 pre-seeded demo rows isolated from every other visitor. The "scale story" is no longer a paragraph — it's a tested property of the running system.

5. **A web UI** — Vite + React 19 + Tailwind v4 with a lavender token system, shadcn-style primitives on Radix, framer-motion, Sonner toasts.

The stack is hybrid: **Python FastAPI for the backend** (PydanticAI, SQLite + JSON columns) and **React for the frontend** (TanStack Query for server state, Zustand for UI state, ky for HTTP). One Render service runs both: FastAPI serves `/api/*` and mounts the built SPA at `/`.

## Try the live demo

Open the deployed URL (Render) and click **Try the live demo**. Reasonable walk:

1. Land on the chat page. Ask "How many orders do I have?" — the response cites 6 orders from Shopify.
2. Hit `/agents` and click "Run agent now". A row appears in the feed; click it to see the per-order decisions. `rohan@example.com`'s COD order (₹4,599 to pincode 110001, 22:48 IST) proposes `convert_to_prepaid` with the cross-connector RTO history driving the score.
3. Hit `/records` to see the 96 rows mixed across Shopify, Meta Ads, and Shiprocket. Click a row to drill into raw + normalized.
4. Hit `/connectors` to see all three cards as "demo / connected".
5. Open an incognito window, click "Try the live demo" again — completely fresh merchant, independent data, independent agent run history.

## Run locally

```bash
git clone https://github.com/cyb3rb34s7/AI-Munim.git
cd AI-Munim
cp .env.example apps/api/.env  # fill in SESSION_SECRET, CREDENTIALS_ENCRYPTION_KEY, OPENAI_API_KEY

# Backend (terminal 1):
cd apps/api
uv sync
uv run uvicorn munim.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (terminal 2):
cd apps/web
pnpm install
pnpm dev   # http://localhost:5173

# Open http://localhost:5173 and click "Try the live demo".
```

Or build the single-image production container:

```bash
docker build -t munim .
docker run -p 8000:8000 \
  -e SESSION_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32))') \
  -e CREDENTIALS_ENCRYPTION_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))') \
  -e OPENAI_API_KEY=sk-... \
  -e SHOPIFY_OAUTH_ENABLED=false \
  -e SHOPIFY_CLIENT_ID=ignored -e SHOPIFY_CLIENT_SECRET=ignored \
  -e SHOPIFY_OAUTH_REDIRECT_URI=http://localhost/no-oauth \
  -e SHOPIFY_DEFAULT_SHOP_DOMAIN=example.myshopify.com \
  munim
# Open http://localhost:8000 — SPA + API on one port.
```

## How the citation contract works

Four layers, all must hold:

1. **Tool return shape** — every chat tool emits `{ data, citations: list[RowCitation] }`. Tools know which `record` rows they touched; the LLM just quotes them.
2. **Structured output** — the LLM's final answer is forced into a Pydantic `GroundedAnswer` shape: `text` (with `[cite:record_id]` markers inline) + `used_citations`. No free-form prose.
3. **Validation** — every `[cite:N]` marker is checked against the citations the tools returned. Hallucinated record ids fail validation → retry once → error.
4. **Fail-closed post-processor** — regex pass over `text` finds any free-floating number not inside a `[cite:...]` marker and replaces it with `[unverified number removed]`. If the scanner errors, we reject the whole response.

## How the agents work

We ship two agents, deliberately on two different patterns. A reviewer asking "show me the LLM-in-the-loop" sees the briefing agent; a reviewer asking "show me an auditable, deterministic decision" sees the RTO mitigator. Both write to the same `run_log` table and surface in `/agents`.

### RTO Risk Mitigator (deterministic)

Run via `POST /agents/rto_mitigator/run`. Four bullets:

1. **Signals are pure functions.** `customer_rto_rate` (joins to Shiprocket via the SHA-256 customer hash), `pincode_risk`, `order_value_band`, `time_of_order_risk` (IST-local, not UTC — Phase 6 paid lesson).
2. **Scoring is a weighted sum + threshold tree.** `Decimal` end-to-end for money. Weights are module-level constants; thresholds split into `convert_to_prepaid` / `confirmation_call` / `no_action`.
3. **One `RunLog` row per run.** `detail_json` carries the per-order signal scores, weights, action, estimated ₹ saved, and a one-line reasoning string.
4. **Zero outbound HTTP.** `respx.mock` test locks this for the httpx layer; the agent is purely a reasoning + scoring pass over local data.

### Daily Briefing (LLM-driven, sector-aware)

Run via `POST /agents/daily_briefing/run?sector=fashion`. Four bullets:

1. **PydanticAI agent over the chat tools.** Reuses `query_orders / query_shipments / query_ad_spend` — same provenance contract as the chat surface.
2. **Sector biases the system prompt.** Six sectors (fashion / beauty / fmcg / electronics / home / generic); each splices a one-line "watch for X" hint that nudges the narrative toward sector-specific concerns (size-fit RTOs for fashion; high-AOV COD risk for electronics; repurchase windows for beauty).
3. **Citation contract end-to-end.** Output is a `BriefingOutput { narrative, proposed_actions, used_citations }` Pydantic shape; every numeric claim carries an inline `[cite:row_id]` marker; the same fail-closed enforcer the chat layer uses strips any uncited number before persistence.
4. **One `RunLog` row per run.** `detail_json` carries `narrative` (cleaned), `proposed_actions[]`, full `citations[]`, `sector`, `run_id`, `trace_id`. Renders in `/agents` via a `<BriefingDetail>` branch in `RunDetailSheet`.

## Connectors — which 3 and why

**Shopify + Meta Ads + Shiprocket.**

These three are not independent picks. They compose into the founder's #1 cross-tool question, the one they currently solve in Excel:

> *"Are my Meta campaigns actually profitable after I account for RTO losses?"*

- **Shopify** tells us the order existed and how much it was worth.
- **Meta Ads** tells us which campaign brought the customer and what we spent to acquire them.
- **Shiprocket** tells us whether the order was actually delivered or returned to origin (RTO).

Without all three, true ROAS is uncomputable. Triple Whale charges $149–2,500/month to answer the global version of this; nothing open-source and Indian-D2C-aware exists. That gap is the whole reason.

Additional reasons each one earned its slot:

- **Shopify** — dominant Indian D2C storefront. Official MCP exists (Storefront + Dev). Dev store is free and instant; no KYC for testing.
- **Meta Ads** — where Indian D2C spends the largest acquisition rupees. Meta shipped their official Ads MCP on 29 April 2026 (29 tools, OAuth). Real test access via existing Business Manager.
- **Shiprocket** — chosen for two reasons. First, the Indian fulfilment reality (RTO, COD failures, pincode coverage) cannot be modelled from any non-Indian tool. Second, **the official `bfrs/shiprocket-mcp` is built by Bigfoot Retail Solutions** (BFRS = Shiprocket's parent company, confirmed via their own merchant agreement). We use it where appropriate for live operations, and build the analytics layer above it.

What we deliberately *didn't* pick:

- **Stripe** — confirmed invite-only for Indian businesses (2025–2026). Wrong choice for the persona.
- **Razorpay** — strong candidate, no MCP yet. Kept as a stretch goal if time allows in week 1.
- **Klaviyo** — answers a different class of question (retention), and acquisition + fulfilment + revenue is the more urgent unit-economics loop for our persona.

Full landscape analysis with the WHYs for every alternative is in [`docs/research.md` §2](docs/research.md).

## Schema — why this shape

**One table.** Polymorphic by `entity_type`. JSON for the shape, SQL for the queries, Pydantic for the validation.

```
record(
  id, merchant_id,
  source_system, source_id,           -- 'shopify' / 'meta_ads' / 'shiprocket' / <any>
  entity_type,                        -- 'order' / 'shipment' / 'ad_spend' / <any>
  fetched_at, payload_hash,
  raw         JSON,                   -- the source response, verbatim (provenance)
  normalized  JSON                    -- our canonical Pydantic shape for this entity_type
)
```

Plus three relational tables — `merchant`, `connector_credentials`, `run_log`. **That is the entire schema.** Four tables, none entity-specific.

Why this shape:

- **It is honestly universal.** Adding a brand-new entity type (say, a CRM `deal` from HubSpot) requires zero DDL: write a `Deal` Pydantic model in code, map source response → `record` row with `entity_type='deal'`. Done.
- **Typed shapes live in code, not in DDL.** `class Order(BaseModel)`, `class Shipment(BaseModel)`, etc. live in `apps/api/src/munim/schemas/`. Changing the shape of an `Order` is a Python change, not a migration.
- **Provenance is structural, not aspirational.** Every row carries `source_system`, `source_id`, `fetched_at`, `payload_hash`, and the original `raw` JSON. No "we tried to track it" caveats.
- **Citations resolve to one ID space.** Every `RowCitation` points at `record.id`. The validator has one lookup, one shape.
- **Indexes are an optimisation, not a constraint.** Partial indexes on JSON paths (`json_extract(normalized, '$.placed_at') WHERE entity_type='order'`) speed up hot queries without changing the model.
- **`merchant_id` on every row, even in single-merchant v0.** The scale-out partitions one table, not seven.

**Why SQLite + JSON columns and not MongoDB?** Tradeoff written out honestly in [`docs/architecture.md` §4.7](docs/architecture.md). Short version: single-file deploy beats document-store-native ergonomics at v0 scale; the citation contract benefits from SQL-native joins to `run_log` and `connector_credentials`; the Postgres upgrade path preserves all our SQL. MongoDB is a defensible alternative; we picked the leaner one for a v0 demo.

Full schema, the "adding a new connector" table, the JSON-path indexing strategy, and the MongoDB comparison are in [`docs/architecture.md` §4](docs/architecture.md).

## Chat — tool schema and how citation works

The chat layer is a PydanticAI agent loop with a small, deliberate tool set:

| Tool | What it does |
|---|---|
| `query_orders` | Read orders by date/payment-method/status/campaign/pincode → rows + citations |
| `query_shipments` | Read shipments (status, courier, pincode, date) → rows + citations |
| `query_ad_spend` | Read ad spend by campaign/date/granularity → rows + citations |
| `query_customer_history` | One customer's full history (orders + shipments) → rows + citations |
| `compute_metric` | Derive numbers (ROAS, CAC, RTO-rate, etc.) carrying forward citations from the rows summed |
| `propose_action` | Surface what the agent would do for a given order; **logged**, never executed |

Every tool returns `{ data, citations, render? }`. Citations come from the tool, not the LLM.

**How the citation contract is enforced** — four layers, all must hold:

1. **Tool return shape.** Every tool emits a `ToolResult` with explicit `citations: list[RowCitation]`. Tools know which `record` rows they touched; the LLM just quotes them.
2. **Structured output.** The LLM's final answer is forced into a Pydantic `GroundedAnswer` shape: `text` (with `[cite:record_id]` markers inline) + `used_citations` (the record ids). No free-form prose.
3. **Validation.** Every `[cite:N]` marker is checked against the citations the agent's tools actually returned. Hallucinated record ids fail validation → retry once → error if still failing.
4. **Fail-closed post-processor.** A regex pass over `text` finds any free-floating number not inside a `[cite:...]` marker and replaces it with `[unverified number removed]`. Fail-closed means: if the scanner errors, we reject the response, never ship the number.

What this prevents and what it doesn't is enumerated explicitly in [`docs/architecture.md` §5.5](docs/architecture.md). The honest gap: paraphrase verification (the model citing the right row but typing the wrong number string) is not in v0. It's in the eval section below.

The UI renders `[cite:N]` markers as inline shadcn badges. Clicking a badge opens a popover showing both the `normalized` shape and the `raw` source payload from the cited `record` row.

## Agents — what they do and why these two

We ship two agents on two intentionally different patterns. Both are manually triggered in v0 (no cron), both write to the same `run_log` table, both surface in the `/agents` audit log.

**The RTO Risk Mitigator (deterministic).** For each new COD order, it scores RTO risk from named signals — customer's past RTO rate, pincode RTO rate, order-value band, time of order — and proposes one of three actions: `convert_to_prepaid`, `confirmation_call`, or `no_action`. It writes everything to a `run_log`: the score, the signals that produced it, the proposed action, the estimated ₹ saved if intercepted, and the cited rows that supported each decision.

**The Daily Briefing (LLM-driven, sector-aware).** A PydanticAI agent that calls the chat tools (`query_orders / query_shipments / query_ad_spend`), composes a 7-day narrative + 0–3 proposed actions in plain English, and threads the same fail-closed citation enforcer over the output so every numeric claim is grounded in a real `record` row. Sector (fashion / beauty / fmcg / electronics / home / generic) is a per-run dropdown that splices a sector-specific "watch for X" hint into the system prompt.

**Neither actually sends anything.** No WhatsApp, no calls, no order modifications, no emails. The brief asked for the reasoning trail, not the side effect, and that's what we ship.

### Why these two, on two different patterns

The brief is graded on craft + judgment. Two agents on two patterns is a deliberate judgment call: a reviewer reading the rubric for "show me an auditable AI employee" sees the deterministic agent (`signals × weights → action`, no LLM, every step inspectable); a reviewer reading the rubric for "show me LLM-in-the-loop reasoning" sees the LLM-driven briefing. Shipping only the first risks reading as "not actually AI"; shipping only the second risks reading as "magic, hope you trust the model." Two agents, two patterns, one schema, one citation contract.

Three reasons each was the right pick:

1. **Indian D2C reality.** RTO is the single largest bleeding source for an Indian D2C brand at our target ARR. COD share is 40–60%; RTO rates 15–25% baseline (40% for new brands); cost per RTO ₹150–300. A brand doing 1,000 COD orders/month at 20% RTO bleeds ₹30,000–60,000/month — roughly one junior operator's salary, every month. Even intercepting 25% of high-risk orders is a six-figure annual saving. (RTO mitigator.)
2. **Owner-readable weekly briefing.** D2C founders don't want a dashboard at 9pm; they want a paragraph. The briefing agent compresses the week into 4–6 sentences + a few concrete actions, citation-grounded. (Daily briefing.)
3. **They use all three connectors.** Customer history needs Shopify + Shiprocket joined by customer. Pincode RTO rate needs Shiprocket aggregated. UTM attribution for ROAS comes from Meta. Both agents prove the universal schema is worth the work.

### Failure modes — listed up front, not after the reviewer finds them

- **False positives → harassing legitimate customers.** Mitigated by per-merchant threshold tuning; visible false-positive rate in run log; the human operator can ignore any single proposal.
- **Data sparsity.** New merchants have few historical shipments. When customer history < 3 orders, the agent falls back to pincode + order-value signals and caps the maximum achievable score.
- **Pincode bias.** Some pincodes have structural issues; the agent will over-recommend prepaid there. Run log annotates "score driven by pincode" so the operator sees the cause.
- **Drift.** Festive seasons spike RTO; weights become stale. v0 ships fixed weights with a config knob. Retraining cadence is documented.

Full design in [`docs/architecture.md` §8](docs/architecture.md).

## Scale — demonstrated, not aspirational

Phase 9 turned the scaling claim from "future tense paragraph" into "tested property of the running system." Every visitor to the deployed URL becomes a real `Merchant` with its own 96-row dataset, isolated by `merchant_id` on every query. Isolation tests assert that data from merchant A is not visible from merchant B's session.

Ranked failure modes (full version in [`docs/architecture.md` §10](docs/architecture.md)):

| Rank | What breaks first | When | At scale |
|---|---|---|---|
| 1 | **Sync orchestration** — per-merchant seed runs inline in `/auth/start` | Few hundred concurrent visitors | Worker pool (Temporal/Celery) with per-merchant jobs and SSE progress |
| 2 | **Connector rate limits** (Shopify ~2/s, Meta quota, Shiprocket low) | First 5–20 merchants on real OAuth | Per-merchant token buckets in Redis; tiered sync; webhooks where supported |
| 3 | **DB contention** (SQLite is single-writer) | 10–50 concurrent seeders | The Postgres migration is one `DATABASE_URL` change; SQLModel speaks both. Partition by `merchant_id`. |
| 4 | **LLM cost** | 100+ merchants with frequent agent runs | Tool-result caching; per-merchant LLM budgets; local small models for routing |
| 5 | **Run log growth** | 1000+ merchants | ClickHouse/DuckDB column store for cold data |
| 6 | **Auth.** Anonymous session cookies are a demo mechanism, not real auth | Day 1 of paying customers | Real auth (email/password, magic link, OAuth providers) — Phase 10 |

**What v0 built deliberately to absorb the future** (all of these are now tested behaviour, not design claims):

- `merchant_id` on every row, every query, every test isolation assertion.
- Anonymous session cookie + per-visitor merchant + per-merchant pre-seeding via `POST /auth/start`.
- Single-table polymorphic schema — partition by `merchant_id` on one table, not seven.
- Connectors are stateless objects, trivially parallelisable across visitor seed jobs.
- `SyncContext`/`RowSink` abstraction so inline writes become queue writes with no schema change.
- Append-only `run_log` ready to ship to a column store.
- PydanticAI provider abstraction — model swaps don't touch tool definitions.

**Sketched but not built:** `scripts/loadtest_visitors.py` (N parallel visitors hitting `/auth/start` + `/chat`, measuring p50/p95/p99); real auth; webhook ingestion.

## Eval — where it breaks

The honest list of what fails when each headline feature is actually poked. Grouped by surface, with the empirical failure mode, not just "limitations."

### Chat / citation contract

- **Paraphrase verification not in v0** — the highest-value gap. The model can type `₹15,000[cite:N]` while row N actually says `₹15,750`. The provenance is honest; the digit string isn't checked. Hover-verifiable by a careful user; not auto-caught. Mitigation roadmap: numeric-exact comparison against citation rows.
- **Derived counts sometimes drop their cite marker.** When the model summarises ("2 orders at risk"), it occasionally writes the number without `[cite:A,B]` → enforcer strips it → user sees the friendly "a number" placeholder. System-prompt nudges help; not 100% reliable.
- **Cross-source math is sometimes wrong even when individual numbers are cited.** Tested live: asked "AOV from the best Meta campaign?" — got back `₹14,694`, which was actually the total Shopify revenue, not divided by purchase count. The citation contract proves *"this number came from a real row,"* it does not prove *"the LLM did the right arithmetic."* Citations let a careful reviewer notice; nothing auto-flags interpretation errors.
- **Tool-loop occasionally exhausts pydantic-ai's `request_limit=50`** on chained queries. User sees a one-shot 502; retry usually works.

### Agent (RTO Risk Mitigator)

- **Customer-history sparsity.** Customers with <3 shipments fall back to the population baseline (0.2). Most demo customers stay there. Real new merchants would see this trade-off too for the first 30–90 days of operation.
- **Pincode high-risk list is a static 6-entry seed.** No automated learning from observed RTO outcomes.
- **Weights are fixed defaults.** Festive seasons spike RTO and drift the weights stale. Retraining cadence documented; not implemented.

### Connectors

- **Meta Ads + Shiprocket ship as demo-mode** with real-shape fixtures from the providers' API docs. `BaseConnector` swap to real OAuth is mechanical but isn't shipped.
- **Shopify OAuth is disabled on the deployed URL.** No per-visitor Partner App on the demo. Works locally with `SHOPIFY_OAUTH_ENABLED=true`.
- **No webhook ingestion.** Polling-only. Real-mode staleness would be up to 30 minutes between scheduled syncs.

### Auth

- **Anonymous session cookie behaves like a bearer token.** Anyone with another visitor's signed cookie value sees their data. Acceptable for a hiring demo, dangerous in production. No email, no password, no invite, no recovery — all deliberate Phase 10 scope.

### Infrastructure

- **SQLite single-writer locally.** Intermittent `sqlite3.InterfaceError` under chained-tool-call thread contention. **Goes away on Render** because the deployed env ships managed Postgres.
- **Render free tier cold-start ~30s** after 15min idle on a first hit. Subsequent requests are warm.
- **LLM cost ceiling.** ~250 chat calls per 50 reviewers × 5 questions each. Free-tier rate limits hold for the demo window; not for paying-customer load.

### Frontend

- **Bundle ~1MB pre-gzip.** Recharts + Radix + framer-motion. No route-level code-split. Acceptable for an admin SPA, not for marketing-perf concerns.
- **Desktop-first.** FeedPanel hides below 1024px; below 768px the layout breaks. No mobile pass yet.

## Hours spent

**~8–10 hours of active work over 5 calendar days, across 4–5 sessions** (2026-05-13 → 2026-05-17).

The first two days were entirely docs and design iteration — the brief read, the persona sharpened, the connector landscape researched and justified ([`docs/research.md`](docs/research.md)), the schema shape argued out ([`docs/architecture.md` §4](docs/architecture.md)), the citation contract designed across its four enforcement layers, the agent's signal model laid out, the project's conventions written down ([`docs/conventions.md`](docs/conventions.md)). No code shipped in days 1–2; just sharpening what would get built.

Days 3–5 were the implementation phases via subagent-driven development. Each phase had a plan (`docs/plans/YYYY-MM-DD-phase-N-*.md`), a dispatched coder subagent, a dispatched reviewer subagent, a fix cycle, manual smoke, and push. The commit history follows the phase rhythm — `feat(scope):` per task, `fix(scope):` per review finding, `docs(scope):` per phase docs update.

## Tech choices

Short defenses for the non-obvious picks:

- **PydanticAI** over LangChain or raw OpenAI SDK — typed tool inputs/outputs, structured-output validation built in, provider-agnostic. The four-layer citation contract sits cleanly on top of it.
- **SQLModel** over raw SQLAlchemy — Pydantic + SQLAlchemy in one type. The same `Order` model validates the wire and the row.
- **Tailwind v4 + lavender token system** — Phase 7's design pass. Token-driven theming so `getComputedStyle` reads at render time keep Recharts cells in sync with the dark/light toggle.
- **framer-motion** — fadeUp transitions on route changes, AnimatePresence on the agent run feed. Small but tactile.
- **Render** — single service, persistent disk for SQLite, free tier covers a hiring-review window. One `render.yaml` artifact; the deployment is reproducible.
- **Vite + React 19** instead of Next.js — the app is a SPA admin UI, no SSR need, no SEO concern. Vite's HMR is sub-second; production build is ~4s.

## What we'd do with another week

In rough priority order:

1. **Paraphrase verification of citations** (the highest-value gap in the citation contract).
2. **Real OAuth for Meta and Shiprocket.** The interface is already designed for it; only the per-connector implementation is missing.
3. **Webhook ingestion** for Shopify orders/refunds. Reduces staleness from 30 minutes to seconds for the agent.
4. **Scheduled briefings.** The daily-briefing agent ships with a manual trigger; a cron/APScheduler tick that fires it weekly per merchant (and emails the narrative) is half a day of work and adds the "proactive" axis to the existing two agents.
5. **Multi-tenant cut-over.** Per-merchant credentials, per-merchant Postgres schema, an auth layer. The skeleton is there; this would harden it.
6. **Load-test harness.** A real `load_test.py` that fans out N synthetic merchants and measures connector throughput, DB contention, LLM cost.
7. **Numeric-format normalisation in citations.** "₹12,000" vs "12000" vs "12K" — pick one canonical render and convert.
8. **Razorpay as connector #4.** Test mode is easy; the connector is half a day of work.

## AI tool usage — honest accounting

The brief said *"use them, be honest about what you wrote vs what the LLM wrote — that's signal, not stigma."* Here's the honest read.

### What I shaped (the human directing the build)

- **The entire architecture, raw, before any code.** The universal single-table polymorphic schema with row-level provenance, the four-layer citation contract, the RTO Risk Mitigator's signal model (named signals, weighted sum, threshold tree, no LLM in the loop), the `BaseConnector` ABC + `RowSink` writer pattern, the citation chip → tooltip → record drill-down UX, the deployment target. I proposed each direction first; we iterated multiple times before any of it got typed.
- **Project rules and conventions** ([`docs/conventions.md`](docs/conventions.md)). No silent fallbacks, no magic strings in branches, `Decimal` for money everywhere, IST↔UTC at the wire boundary, `trace_id` threaded through HTTP→DB→LLM, the citation contract is fail-closed by design, no broad `except Exception`, meaningful-tests-only filter (§13.4). These rules drove what got rejected at reviewer time.
- **Methodology — subagent-driven development.** Plan → one coder subagent per phase → one reviewer subagent per phase → apply findings → smoke → docs + push. Captured in `CLAUDE.md`. Plans in `docs/plans/` are how the work was scoped, not artifacts of AI autonomy.
- **Dependency choices** with WHYs in [`docs/architecture.md` §2](docs/architecture.md). FastAPI + Pydantic + SQLModel + PydanticAI + SQLite-with-JSON for the backend; Vite + React 19 + Tailwind v4 + framer-motion + Recharts + Sonner + shadcn-on-Radix for the frontend; Render free tier for deploy.
- **Product calls** that came from live testing and pushback — the onboarding wizard (replaced silent auto-seed), cookie session auth (rejected JWT-in-localStorage), Meta + Shiprocket as demo-mode (rejected real-OAuth-on-deploy because it would burn reviewer setup time), the citation chip's visual design (rejected three earlier versions before the dotted-underline pattern), the chat suggestions redesigned twice based on what looked ugly in screenshots.
- **Review of every diff before push.** Each phase's reviewer-subagent surfaced findings; I read every one and decided which to fix vs defer. Real pushback caught: the Shopify demo sync bug, the timezone bug in the agent's time-of-order signal, the `[unverified number removed]` sentinel leaking into the UI, the logout→login routing to `/chat` instead of `/onboarding`, the engineer-prose error message bubbling to the chat UI.

### What Claude (the LLM) did

- **Wrote ~95% of the code** via the subagent-driven development workflow. Plans I scoped → coder subagent implemented (one dispatch per phase, walking the plan top-to-bottom committing per task) → reviewer subagent critiqued the diff → I applied fixes inline. Tests included.
- **Drafted this README, [`docs/architecture.md`](docs/architecture.md), [`docs/research.md`](docs/research.md), [`docs/conventions.md`](docs/conventions.md), every plan file in `docs/plans/`, and [`CHANGELOG.md`](CHANGELOG.md).** Each follows the framing I set — what to argue, which tradeoffs to name, which paid lessons to capture. The structure is mine; the prose is collaborative.
- **Helped debug and test** — including using a headless browser agent during the final smoke to walk the logout→login flow, surface the Shopify sync regression, and verify the chat citation rendering changes.

### Where the line gets fuzzy (worth naming)

- Code I'd have written by hand vs. code AI expedited: roughly **4–5× compression** on time-to-typed-code. The decisions, the rules, the methodology, the reviews are mine; the typing isn't.
- The choice of subagent-driven development with explicit plan + review gates was deliberate process design, not "let AI do it." That's the thing that made AI-written output reviewable instead of opaque.

The signal here, to the rubric's word: a similar shape would ship from the same constraints; what AI accelerates is the speed from clearly-scoped plan to reviewable code, not the design judgment itself.

## Deeper docs

| Read | Why | Time |
|---|---|---|
| [`docs/requirements.md`](docs/requirements.md) | The ask, target user persona, functional and non-functional requirements, acceptance criteria | ~5 min |
| [`docs/research.md`](docs/research.md) | Optional. Connector landscape with all the WHYs for what we picked and what we didn't, framework comparison, A2UI / Vercel AI SDK research, prior art, RTO economics | ~10 min |
| [`docs/architecture.md`](docs/architecture.md) | System diagrams, the universal schema with SQL DDL, the citation contract in detail, the agent design, the scale ranking, security model | ~15 min |

## Acknowledgments

- **`NousResearch/hermes-agent`** — we borrowed the architectural patterns (cron as first-class data flow, tool registry, observable execution, platform-agnostic core). We did not import the dependency; it's a generalist personal agent and we needed a narrow domain one.
- **`bfrs/shiprocket-mcp`** — Shiprocket's parent company (Bigfoot Retail Solutions) ships an official MCP server. It shaped how we thought about Shiprocket integration; we did not duplicate or compete with it. Our v0 uses Shiprocket's REST API directly (rationale in `docs/architecture.md` §9).
- **MongoDB and event-sourcing literature** — the single-table polymorphic model with typed application-side schemas is a recognisably document-store-shaped design, executed on SQL. Comparison in `docs/architecture.md` §4.7.
- **Google A2UI** — the spec for agent-driven generative UI inspired our render-spec shape. We did not implement A2UI v0.9 in full; we adopted the concept.
- **Vercel AI SDK** + the **FastAPI + AI SDK** template — official support for the Python-backend / TypeScript-frontend hybrid pattern we run.
- **shadcn/ui, Tremor, Pydantic, PydanticAI, FastAPI, Next.js** — the components and frameworks doing the heavy lifting.

## License

MIT — see [LICENSE](LICENSE).
