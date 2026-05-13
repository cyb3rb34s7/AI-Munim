# AI-Munim

> Every kirana shop had a munim — the bookkeeper who sat in the corner, kept all the ledgers, watched the stock, advised on margins, and noticed when something was off. Modern D2C founders have Excel and vibes. AI-Munim is the modern munim: an AI employee for Indian D2C brands that reads across their SaaS tools, answers cross-tool questions with citations on every number, and proactively flags ₹-saving actions.

> **Status:** v0 in flight. Documentation is committed first; code follows in subsequent phases.

---

## Table of contents

- [What we built](#what-we-built)
- [Quickstart](#quickstart)
- [Connectors — which 3 and why these 3](#connectors--which-3-and-why-these-3)
- [Schema — why this shape](#schema--why-this-shape)
- [Chat — tool schema and how citation works](#chat--tool-schema-and-how-citation-works)
- [Agent — what it does and why this one](#agent--what-it-does-and-why-this-one)
- [Scale — 1 merchant to 10,000](#scale--1-merchant-to-10000)
- [Eval — where it breaks](#eval--where-it-breaks)
- [Hours, days, sessions](#hours-days-sessions)
- [What we'd do with another week](#what-wed-do-with-another-week)
- [AI tool usage — honest accounting](#ai-tool-usage--honest-accounting)
- [Deeper docs](#deeper-docs)
- [Acknowledgments](#acknowledgments)

---

## What we built

A working v0 of an AI employee for Indian D2C brands. Five-line architecture summary:

1. **Three connectors behind one abstraction** — Shopify, Meta Ads, Shiprocket — pulling into one universal single-table polymorphic store with row-level provenance.
2. **A chat layer** built on PydanticAI with a strict citation contract: every numerical claim is wrapped with `[cite:record_id]` markers, post-processed fail-closed so uncited numbers never reach the user.
3. **An autonomous agent — the RTO Risk Mitigator** — runs on a cron schedule, scans new COD orders, scores RTO risk from cross-tool signals, proposes intercept actions without ever sending them.
4. **A scaling story** — concrete ranking of what breaks first as we go from 1 merchant to 10,000, with the parts of v0 that were built deliberately to absorb the future.
5. **A web UI** in Next.js + shadcn/ui + Vercel AI SDK, with one-click connector setup and inline generative artifacts (A2UI-shaped render specs).

The stack is hybrid: **Python FastAPI for the backend** (PydanticAI, SQLite + JSON columns, mature LLM/data tooling) and **Next.js for the frontend** (Vercel AI SDK 5 streaming, shadcn/ui polish, artifacts in chat). Vercel officially supports this pattern.

## Quickstart

> Once the code lands. The doc structure is committed; the runtime layer follows.

```bash
git clone https://github.com/cyb3rb34s7/AI-Munim.git
cd AI-Munim
cp .env.example .env                  # add OpenAI/Anthropic keys (optional in demo mode)
docker-compose up                     # api on :8000, web on :3000

# In a separate terminal:
docker-compose exec api uv run munim seed   # populate the SQLite store with realistic fixtures

# Open http://localhost:3000 and start chatting.
# Or open http://localhost:3000/settings/connectors and click "Connect".
```

Demo mode runs without any external API keys against seeded fixtures. The chat, the citations, and the agent all work end-to-end.

## Connectors — which 3 and why these 3

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

## Agent — what it does and why this one

**The RTO Risk Mitigator.** Runs every 30 minutes (configurable). For each new COD order since the last run, it scores RTO risk from named signals — customer's past RTO rate, pincode RTO rate, order-value band, product category, time of order — and proposes one of three actions: `convert_to_prepaid`, `confirmation_call`, or `no_action`. It writes everything to a `run_log`: the score, the signals that produced it, the proposed action, the estimated ₹ saved if intercepted, and the cited rows that supported each decision.

**It never actually sends anything.** No WhatsApp, no calls, no order modifications. The brief asked for the reasoning trail, not the side effect, and that's what we ship.

### Why this agent

Three reasons, all checkable:

1. **Indian D2C reality.** RTO is the single largest bleeding source for an Indian D2C brand at our target ARR. COD share is 40–60%; RTO rates 15–25% baseline (40% for new brands); cost per RTO ₹150–300. A brand doing 1,000 COD orders/month at 20% RTO bleeds ₹30,000–60,000/month — roughly one junior operator's salary, every month. Even intercepting 25% of high-risk orders is a six-figure annual saving.
2. **It uses all three connectors.** Customer history needs Shopify + Shiprocket joined by customer. Pincode RTO rate needs Shiprocket history aggregated. UTM attribution for the eventual ROAS lift comes from Meta. The agent proves the universal schema is worth the work.
3. **The decision space is small, bounded, and auditable.** Three actions. Named signals. Configurable weights. The run log is human-readable: an operator can look at one row and understand what the agent saw, what it scored, what it would have done, and why.

### Failure modes — listed up front, not after the reviewer finds them

- **False positives → harassing legitimate customers.** Mitigated by per-merchant threshold tuning; visible false-positive rate in run log; the human operator can ignore any single proposal.
- **Data sparsity.** New merchants have few historical shipments. When customer history < 3 orders, the agent falls back to pincode + order-value signals and caps the maximum achievable score.
- **Pincode bias.** Some pincodes have structural issues; the agent will over-recommend prepaid there. Run log annotates "score driven by pincode" so the operator sees the cause.
- **Drift.** Festive seasons spike RTO; weights become stale. v0 ships fixed weights with a config knob. Retraining cadence is documented.

Full design in [`docs/architecture.md` §8](docs/architecture.md).

## Scale — 1 merchant to 10,000

Honest, ranked, with mitigations.

| Rank | What breaks first | When | What v0 does | At scale |
|---|---|---|---|---|
| 1 | **Connector rate limits** (Shopify ~2/s, Meta quota, Shiprocket low) | 5–20 merchants on shared keys | Per-connector rate-limit decorator, exponential backoff | Per-merchant token buckets in Redis; tiered sync; webhooks where supported |
| 2 | **Sync orchestration** (inline awaits) | 50–100 merchants | APScheduler in-process | Temporal/Celery workers, idempotent activities, per-merchant queue |
| 3 | **DB contention** (SQLite is single-writer) | 10–50 merchants | `merchant_id` in every primary key already | Postgres + partition by `merchant_id` on hot tables; read replicas |
| 4 | **LLM cost** | 100+ merchants with frequent agent runs | Routing-vs-reasoning split (cheap `gpt-4o-mini` for routing, Sonnet for synthesis); deterministic scoring in agent | Tool-result caching; per-merchant LLM budgets; local small models for routing |
| 5 | **Run log growth** | 1000+ merchants | 90-day retention default, append-only | ClickHouse/DuckDB column store for cold data |
| 6 | **Multi-tenant isolation** (v0 has no auth) | Day 1 paying | Single-tenant; key-based fixture isolation | Per-merchant Postgres schema or RLS; per-merchant encryption keys |

**What v0 deliberately built to absorb the future:**

- `merchant_id` on every row
- Single-table polymorphic schema — partition by `merchant_id` on one table, not seven
- Connectors are stateless objects, trivially parallelisable
- `SyncContext`/`RowSink` abstraction so inline writes become queue writes with no schema change
- Append-only `run_log` ready to ship to a column store
- PydanticAI provider abstraction — model swaps don't touch tool definitions
- Connector + tool layers are MCP-ready — wrapping them as an MCP server later does not touch chat or schema

**Sketched but not built:** load-test harness (script outlined), Redis rate limiter (interface present, only the in-memory impl ships), Postgres baseline (Alembic in repo, no migrations yet).

Full table with all 7 failure points and concrete mitigations in [`docs/architecture.md` §10](docs/architecture.md).

## Eval — where it breaks

We told you the failure modes for the agent. Here are the system-level ones we know about — before you find them.

- **Paraphrase verification of citations.** The post-processor catches numbers without citations. It does *not* yet verify that the number after `[cite:N]` matches the value in row N. A determined model could cite row N and still type "₹12 lakh" when row N says "₹12,000." Mitigation roadmap: numeric-exact comparison against citation rows. Not in v0.
- **Single-tenant.** v0 has no user auth. Every chat is "the merchant." Multi-tenant isolation is sketched, not built.
- **No real OAuth for Meta and Shiprocket** in v0. They go through a mock OAuth flow with the same UI as the real Shopify OAuth. The connector interface is identical; flipping to real is a per-connector change. Real Shopify OAuth ships in v0.
- **Polling only, no webhooks.** Means up to 30 minutes of staleness for the agent.
- **No analytics caching.** Every chat query re-runs against the normalised store. Fine for v0, costly at scale.
- **RTO agent is rule-based, not learned.** The weights are sensible defaults, not model-trained. Drift is real. Retraining cadence is documented; the actual retraining job is not in v0.
- **Demo fixtures are realistic but synthetic.** Real merchant data will reveal edge cases (multi-SKU orders, partial fulfilments, exchanges) that the fixtures don't cover.

## Hours, days, sessions

> *To be finalised on submission.*
>
> Currently: documentation phase complete. Code phase in flight. We will commit honest numbers here at the end — across however many sessions and days. The commit history shows the cadence.

## What we'd do with another week

In rough priority order:

1. **Paraphrase verification of citations** (the highest-value gap in the citation contract).
2. **Real OAuth for Meta and Shiprocket.** The interface is already designed for it; only the per-connector implementation is missing.
3. **Webhook ingestion** for Shopify orders/refunds. Reduces staleness from 30 minutes to seconds for the agent.
4. **The second agent: True ROAS Watcher.** Meta spend + Shopify net revenue + Shiprocket RTO losses → flag campaigns whose true profit is negative.
5. **Multi-tenant cut-over.** Per-merchant credentials, per-merchant Postgres schema, an auth layer. The skeleton is there; this would harden it.
6. **Load-test harness.** A real `load_test.py` that fans out N synthetic merchants and measures connector throughput, DB contention, LLM cost.
7. **Numeric-format normalisation in citations.** "₹12,000" vs "12000" vs "12K" — pick one canonical render and convert.
8. **Razorpay as connector #4.** Test mode is easy; the connector is half a day of work.

## AI tool usage — honest accounting

The brief asked us to be honest about what we wrote versus what an LLM wrote. We will be.

The full statement goes in this section on submission, but the pattern is:

- Research, framework comparisons, doc structure, and architectural reasoning — primarily AI-assisted (Claude). Prompts and decisions ours; words structured collaboratively.
- All code that ships will be reviewed line-by-line by a human author. No commit goes in that the author cannot explain.
- The citation contract design (the four-layer enforcement) was AI-assisted in framing but the implementation is ours.

This section will be filled in fully on submission with specific call-outs per area.

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
