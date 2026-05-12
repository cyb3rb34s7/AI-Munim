# Requirements

## 1. The Ask, in our words

A D2C founder runs their business across a long tail of SaaS tools: a storefront (Shopify), an ads tool (Meta), a logistics aggregator (Shiprocket), a payments gateway, a marketing tool, a customer support tool, and a few more. To answer one cross-tool question — *"Are my Meta campaigns actually profitable once I account for returns?"* — they spend half an hour stitching exports in Excel. Most of the time they don't bother. They run on vibes.

The brief asks for a working v0 of an AI employee for this founder. Five hard requirements (paraphrased):

1. **At least 3 proper connectors** to different SaaS sources, behind one shared abstraction.
2. **A universal data model** that normalises across sources. Provenance on every row.
3. **A chat layer** with a tool-use loop. Every numerical claim cites the source rows. Uncited numbers do not survive to the user.
4. **At least one autonomous agent** that watches the data and proposes a ₹-saving or ops-saving action. Reasoning visible, no real side effects.
5. **A scalability story** for one merchant today and ten thousand tomorrow. What breaks first. What we built to absorb it.

What we are scored on, equally: how well we build (craft) and what we chose to build (judgment).

## 2. Target user

A single, specific persona keeps every other decision honest.

| Attribute | Value |
|---|---|
| Role | Founder / co-founder of a D2C brand |
| Geography | India |
| Annual revenue | ₹50 lakh to ₹5 crore (early to growth stage) |
| Stack | Shopify (storefront) + Meta + Google Ads (acquisition) + Shiprocket (fulfilment) + Razorpay (payments) + Klaviyo or WhatsApp tools (engagement) + Tally or Zoho Books (accounting). Typical 6–10 tools. |
| COD share of orders | 40–60% (representative of Indian D2C) |
| Team | 2–8 people. Founder is also the operator. No dedicated data analyst. |
| Current behaviour | Opens 4–6 dashboards a day. Exports CSVs for any cross-tool question. Stops bothering for most. |
| Trust threshold | Will not act on AI output unless they can see the source rows that produced the number. |

Every product decision in this repo is justified by this persona. If a feature does not help this user save money or hours, we did not build it.

## 3. In scope

- Three connectors: Shopify, Meta Ads, Shiprocket. One shared interface, swappable.
- A universal database schema with row-level provenance on every record.
- A chat layer with a strict citation contract: every number traceable to specific rows.
- One autonomous agent: the RTO Risk Mitigator (Return-to-Origin risk on COD orders).
- A scaling narrative with a real harness or a credible sketch.
- A web UI for connector management (one-click "Connect" flow) and a chat surface with inline artifacts.
- A demo mode that runs against seeded fixtures so a reviewer with no API keys can still see the system work.

## 4. Out of scope (deliberate)

- Production-grade multi-tenancy (we describe the path; v0 is single-tenant).
- Real fulfilment side-effects: the agent **never** sends a WhatsApp message, places a call, or modifies an order. It only logs the proposed action.
- A fourth connector. Razorpay is a stretch goal if time remains; not on the critical path.
- User authentication and SSO. Single-user demo for v0.
- Real-time webhooks. v0 uses scheduled pulls; webhook upgrade path is described.
- Mobile UI. Desktop-first.
- Internationalisation. English + Indian context (₹, IST, pincode).

## 5. Functional requirements

Each FR maps to a hard requirement in the brief.

### FR-1. Connector abstraction (Brief req #1)

- FR-1.1. Define a single `BaseConnector` interface with the same lifecycle for all sources: `authenticate`, `validate_credentials`, `sync_full`, `sync_incremental`, `list_resources`.
- FR-1.2. Provide three concrete implementations: `ShopifyConnector`, `MetaAdsConnector`, `ShiprocketConnector`.
- FR-1.3. Any new connector can be added by implementing the same interface; no changes elsewhere in the system are required.
- FR-1.4. Each connector is responsible for handling its own rate limits, retries, and pagination internally.
- FR-1.5. Connectors emit rows into the universal schema, not into source-specific tables. They map their payload to the canonical shape on the way in.

### FR-2. Universal data model with provenance (Brief req #2)

- FR-2.1. Define canonical entities: `merchant`, `order`, `order_item`, `customer`, `product`, `shipment`, `ad_campaign`, `ad_spend_daily`, `payment`.
- FR-2.2. Every row carries provenance fields: `source_system`, `source_id`, `merchant_id`, `fetched_at`, `payload_hash`.
- FR-2.3. The original payload from the source is preserved in a `raw_payload` table, keyed by `(source_system, source_id, fetched_at)`. Citations reference these immutable rows.
- FR-2.4. Idempotency: re-running a sync does not duplicate rows. Updates are applied by `(source_system, source_id)`.
- FR-2.5. The schema is source-agnostic. Adding a new payment provider does not require renaming `order.total_inr` to something else.

### FR-3. Chat layer with citation contract (Brief req #3)

- FR-3.1. Expose a small, explicit set of tools to the LLM (see `docs/architecture.md` for the full schema): `query_orders`, `query_shipments`, `query_ad_spend`, `query_customer_history`, `compute_metric`, `propose_action`.
- FR-3.2. Every tool returns a typed object containing `data`, `citations` (a list of row references), and an optional `render` spec for the UI.
- FR-3.3. The LLM is required, via system prompt and structured output schema, to attach citations to every numerical claim in its final answer.
- FR-3.4. A post-processor (the **citation enforcer**) runs over every model reply: any number that is not attached to a valid citation is replaced with a `[unverified number removed]` token before the user sees it.
- FR-3.5. The UI renders citations as inline badges. Clicking a citation reveals the underlying rows and the raw payload.
- FR-3.6. Responses stream token-by-token to the UI. Artifacts (tables, charts, action cards) appear inline as the relevant tool call resolves.

### FR-4. Autonomous agent: RTO Risk Mitigator (Brief req #4)

- FR-4.1. The agent runs on a cron schedule (every 30 minutes by default; configurable).
- FR-4.2. On each run it scans new COD orders received since the previous run, joining data from Shopify (order, customer) and Shiprocket (historical shipment outcomes, pincode statistics).
- FR-4.3. For each order it computes an RTO risk score using explicit, named signals (customer history, pincode RTO rate, order value bucket, product category, time-of-order). The signal weights and the decision threshold are configurable and visible in the run log.
- FR-4.4. It proposes one of three actions per order: `convert_to_prepaid`, `confirmation_call`, or `no_action`. The proposed action includes an estimated ₹ saved if the intercept succeeds.
- FR-4.5. The agent **does not** dispatch any message, call, or order modification. It writes the proposed action and full reasoning trace to a `run_log` table.
- FR-4.6. Failure modes (false positives → harassed legitimate customers; data sparsity → over-confident scores; pincode bias) are listed explicitly in `docs/architecture.md` and in the README.

### FR-5. Scale story (Brief req #5)

- FR-5.1. The README and `docs/architecture.md` describe what breaks first as the system scales from 1 merchant to 10,000.
- FR-5.2. The system is implemented in a way that makes the per-merchant scale-out path obvious: a `merchant_id` is part of every primary key, every connector run is scoped to one merchant, all queries are merchant-scoped.
- FR-5.3. A minimal load-test harness exists or, if not built, is sketched concretely (commands, expected results, what we'd measure).

## 6. Non-functional requirements

### NFR-1. Performance

- NFR-1.1. Chat: first token in ≤ 2.5s p50 on a warm database. End-to-end answer for a typical question in ≤ 12s p50.
- NFR-1.2. Sync: a full sync of one merchant (Shopify orders + Meta ad spend + Shiprocket shipments) completes in ≤ 5 min for a merchant with under 10,000 orders. Incremental syncs in ≤ 30s.
- NFR-1.3. Agent: a single RTO scoring run for one merchant completes in ≤ 60s for up to 200 new orders per scan.

### NFR-2. Reliability

- NFR-2.1. Connector syncs are idempotent. Re-running a sync after partial failure produces a consistent state.
- NFR-2.2. Rate-limited or transient errors are retried with exponential backoff and a budget. Permanent errors are surfaced with a clear cause.
- NFR-2.3. The citation enforcer is fail-closed: if the post-processor errors, the response is rejected rather than shown unverified.

### NFR-3. Scalability

- NFR-3.1. v0 runs on a single SQLite instance and a single process. This is acceptable for one merchant.
- NFR-3.2. The data model and code are designed so the migration to Postgres + a queue-based sync worker + per-merchant token buckets requires no schema rewrites, only configuration and infra.
- NFR-3.3. The known scaling failure points are enumerated honestly (connector rate limits, DB contention, LLM cost, run-log growth) with the mitigation for each.

### NFR-4. Security

- NFR-4.1. OAuth tokens and API keys are stored in a dedicated `connector_credentials` table that is never returned by any tool, never logged, never sent to the LLM.
- NFR-4.2. Secrets in development are sourced from `.env` files. `.env` is git-ignored. `.env.example` is committed with empty values.
- NFR-4.3. Demo mode never requires real credentials.
- NFR-4.4. Raw payloads stored in `raw_payload` may contain PII (customer phone, address). They are stored locally and never sent to the LLM. The LLM only sees normalised, scoped projections.

### NFR-5. Observability

- NFR-5.1. Every chat conversation, every tool call, and every agent run is persisted to a `run_log` table with timestamps, inputs, outputs, latency, and (where applicable) provider/model.
- NFR-5.2. The agent run log is human-readable: an operator can read a single row and understand what the agent saw, what it scored, what it would have done, and why.
- NFR-5.3. The citation enforcer logs every number it stripped, so we can later analyse how often the LLM tries to hallucinate.

### NFR-6. Operability

- NFR-6.1. `docker-compose up` runs the entire system locally.
- NFR-6.2. A `seed` command populates the database with realistic fixture data so the demo works offline.
- NFR-6.3. The CI pipeline runs lint, typecheck, and tests on every push.

### NFR-7. Honesty

- NFR-7.1. The README explicitly lists where the system breaks. The list is not aspirational; it is what we know.
- NFR-7.2. The README declares what was written by us versus written by an LLM, as the brief requests.
- NFR-7.3. The agent's failure modes are listed before any reader is asked to trust it.

## 7. Acceptance criteria

The v0 is complete when a reviewer can:

1. Clone the repo and run `docker-compose up`.
2. Open the web UI, see three connector cards, click "Connect" on each (mock or real OAuth depending on the connector), and see a successful sync result.
3. Ask the chat *"Which of my Meta campaigns are unprofitable after RTO losses?"* and receive a streamed answer where every number has a clickable citation.
4. Click any citation and see the underlying source rows and raw payload.
5. Wait for or trigger an agent run and read a populated `run_log` containing at least one structured action proposal with reasoning.
6. Read the README in ≤ 5 minutes and understand: what we built, why these 3 connectors, why this agent, what breaks first at scale, where we know it's weak.

## 8. Mapping back to scoring axes

| Brief scoring axis | How this document supports it |
|---|---|
| Judgment | Section 2 (persona) and Section 4 (out of scope) make our choices defensible. |
| Speed | Documentation-first reduces rework; commit history will reflect steady cadence. |
| Connector abstraction | FR-1 spells out one interface, three implementations, swappable. |
| Schema discipline | FR-2 lists provenance fields explicitly. NFR-4 isolates raw payloads. |
| Chat grounding | FR-3 defines the citation contract and the fail-closed enforcer. |
| Agent design | FR-4 enumerates trigger, data, decision, action. Failure modes called out. |
| Scale thinking | FR-5 plus NFR-3 commit to a concrete scaling story. |
| Eval honesty | NFR-7 makes admitted weakness a first-class requirement. |
