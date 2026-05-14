# Changelog

> Append-only. Newest entry at the top. Every meaningful change in this repo has an entry here, written in the same commit as the change.
>
> **Why this file exists:** when something breaks, "what did we change recently?" is the first question. `git log` answers in minutes; this file answers in seconds. It's also where we document deliberate fallbacks and tradeoffs, so a future reader (and a future reviewer of the assignment) can see the reasoning without spelunking.

## Format

```
## YYYY-MM-DD — short title (kebab-case ok)

**What changed:** one-line summary of the diff.
**Why:** the reason. Cite a requirement, a problem in context.md, or a user request.
**Files touched:** load-bearing files only. Not exhaustive.
**Reverts cleanly?:** yes / no / partially (with reason).
```

Multiple entries on the same day are fine; keep newest at the top of that day's group.

---

## 2026-05-14 — Phase 6 review fixes

**What changed:** Reviewer subagent surfaced 3 CRITICAL + 9 IMPORTANT findings against `docs/conventions.md`. All addressed in one fix commit. Highest-value catches:
- **Timezone bug in `time_of_order_risk`** — was reading `.hour` on a UTC-normalized datetime, so a 23:45 IST order scored as "evening" (18:00 UTC). Fixed by converting to `Asia/Kolkata` before reading the hour; raises on naive timestamps.
- **Magic string `"rto"` in branching** — added `FulfillmentStatus` StrEnum; `customer_rto_rate` and test fixtures now go through the enum.
- **Dead `AGENT_RUN_FAILED` error code** — regression of the Phase 3 paid lesson. Wrapped `agent.run` in a narrow `(KeyError, ValueError)` except → typed `AgentRunFailedError` with a test that exercises the wrap on malformed records.
- **Decimal money discipline** — score now computed in `Decimal` end-to-end so the rupee math never touches float (§8.1).
- **`AgentRunNotFoundError` was reusing `record.not_found`** — added `AGENT_RUN_NOT_FOUND` for clean frontend branching (§4.3).
- **Unreachable `category` weight** — dropped and renormalized to (value=0.28, pincode=0.33, time=0.17, customer=0.22); run-log weights now honestly reflect what scored.
- **Silent `""` fallback for missing `customer_source_id`** — replaced with explicit `None` + diagnostic flag (§10).
- **`assert`s as runtime contracts** — replaced with explicit `if x is None: raise RuntimeError(...)`; asserts vanish under `python -O`.

**Test count:** 162 → 168 (+6: UTC-Z late_night, naive-timestamp raise, customer-id-missing, two AgentRunFailedError wraps, Decimal-cents invariant).

**Deps:** added `tzdata>=2024.2` (Windows ZoneInfo needs it).

**Known limitation documented:** `test_agent_makes_zero_outbound_http_calls` uses `respx.mock` which only intercepts httpx; a future contributor switching to `requests`/`urllib` would slip past. Today the project is httpx-only so the guarantee holds.

**Files touched:** `apps/api/src/munim/agents/rto_mitigator/{signals,scoring,agent}.py`, `apps/api/src/munim/modules/agent_runs/{service.py,tests/test_service.py}`, `apps/api/src/munim/shared/constants.py`, `apps/api/pyproject.toml`, plus test files for each.

**Reverts cleanly?:** yes — single fix commit.

---

## 2026-05-14 — Phase 6: RTO Risk Mitigator agent (backend)

**What changed:** New `apps/api/src/munim/agents/rto_mitigator/` package — pure-function signal extractors (`order_value_bucket`, `pincode_risk`, `time_of_order_risk`, `customer_rto_rate`), weighted scoring with threshold tree (`convert_to_prepaid` >= 0.6, `confirmation_call` >= 0.4, else `no_action`), and a deterministic orchestrator that scans COD orders, scores each, and writes ONE `RunLog` row per agent run containing the full per-order decision list in `detail_json`. New `modules/agent_runs/` exposes `POST /agents/{name}/run`, `GET /agent-runs`, `GET /agent-runs/{id}` (all under the standard envelope). New `AgentName` + `AgentActionType` StrEnums in `shared/constants.py` so the action set is type-checked. The agent is deterministic (no LLM) by design — auditable, cheap, predictable; the brief asks for visible reasoning, which the run log provides as exact math.

**No side effects:** dedicated test `test_agent_makes_zero_outbound_http_calls` uses `respx.mock` so any outbound HTTP call from the agent would be intercepted and fail. This locks the brief's "AI employee proposes, doesn't dispatch" constraint at the test level.

**Test count:** 135 -> 162 (+27): 9 signals + 6 scoring + 7 agent + 5 endpoint.

**Files touched:** `apps/api/src/munim/agents/**`, `apps/api/src/munim/modules/agent_runs/**`, `apps/api/src/munim/shared/constants.py`, `apps/api/src/munim/main.py`, `apps/api/scripts/seed_cod_order.py`.

**Demo seeding:** `apps/api/scripts/seed_cod_order.py` adds one high-RTO-risk COD order to the local DB. Shopify dev-store quirk: `draftOrderComplete(paymentPending: true)` does not populate `payment_gateway_names`, so the mapper defaults to PREPAID and the agent filters the order out. Until we have a real COD path from Shopify, this local seed is documented as demo-only. Run with `uv run python scripts/seed_cod_order.py` from `apps/api/`.

**Out of scope (deferred):** LLM-driven decisions (deterministic by design); Shiprocket-backed customer history (Phase 10 — for now < 3 orders returns population baseline 0.2); `product_category` signal (needs schema change, weight 0.1 so impact is small); cron auto-fire (manual trigger only in v0); per-decision RunLog rows (one-per-run is the design); frontend Agent Runs page (Phase 8).

**Reverts cleanly?:** yes — drop `agents/` and `modules/agent_runs/`, revert `constants.py` and `main.py`.

---

## 2026-05-14 — Phase 5: chat layer with citation contract (backend)

**What changed:** Backend chat surface live. New `apps/api/src/munim/chat/` package: `RowCitation` + `ToolResult` + `GroundedAnswer` + `AnsweredQuestion` types; the fail-closed citation enforcer that strips any numeric claim not immediately followed by `[cite:row_id]` markers; typed tools (`query_orders`, `compute_metric`, `propose_action`) backed by real `record` rows; the PydanticAI agent orchestrator (OpenAI gpt-4o-mini default, override via `OPENAI_CHAT_MODEL` env) with the citation-contract system prompt and `GroundedAnswer` structured output. New `modules/chat/` exposes `POST /chat/messages`. All tests use PydanticAI's `TestModel` for the LLM — zero real OpenAI calls in CI; one optional env-gated live test for the operator.

**The citation contract has 4 layers, all in place:**
1. Tool return shape — every tool returns `ToolResult{data, citations}`.
2. System prompt — explicit instruction to wrap every number in `[cite:N]`.
3. Structured output — `GroundedAnswer` forces the model into `{text, used_citations}`.
4. Fail-closed post-processor — uncited numbers stripped, hallucinated row ids reject the answer.

**Test count:** 95 → 126 (+31 new): 6 types + 13 enforcer + 8 tools + 2 agent + 2 router. Every enforcer test pins a specific LLM hallucination class.

**PydanticAI version installed:** 1.96.0 (the plan was written for >=0.4; 1.96.0 is the latest stable and is backward-compatible with the plan's API surface with one adjustment — `ToolReturnPart` imported from public `pydantic_ai.messages`, not the private `_agent_graph._messages`). `TestModel(call_tools=[...])` controls which tools the mock model invokes; `custom_output_args=GroundedAnswer(...)` returns the canned structured output.

**Files touched:** `apps/api/src/munim/chat/{types,enforcer,tools,agent}.py` + tests; `apps/api/src/munim/modules/chat/{schemas,service,router}.py` + tests; `apps/api/src/munim/shared/{config,constants}.py`; `apps/api/pyproject.toml` (pydantic-ai); `.env.example`; `apps/api/src/munim/main.py` (router register).

**Reverts cleanly?:** yes — drop the new packages, revert the modified ones, drop the dep.

---

## 2026-05-14 — Phase 4: real Shopify OAuth + Admin API

**What changed:** Replaced the Shopify connector's OAuth + Admin API stubs with the real flow. `shared/crypto.py` adds AES-GCM encryption (for the access token in `connector_credentials.auth_blob_encrypted`), HMAC-signed state tokens (so we don't need a `oauth_state` table), and Shopify-style HMAC callback verification. `modules/connectors/oauth_shopify.py` adds the Shopify-specific OAuth helpers — `build_shopify_authorize_url` and `exchange_shopify_code`. New endpoints `POST /api/connectors/shopify/oauth/init` and `GET /api/connectors/shopify/oauth/callback` close the loop with a 303 redirect back to `/connectors?connected=shopify`. `ShopifyClient.iter_orders` now has a real path with the `X-Shopify-Access-Token` header, `Link`-header cursor pagination, and 429 retry honouring `Retry-After`. Frontend gains "Connect to your store" alongside "Connect (demo)" on the Shopify card, plus a modal asking for the shop subdomain and a banner showing post-OAuth success.

**Refactor:** `BaseConnector` ABC dropped `authorize_url` and `exchange_code` — OAuth shapes vary per provider and forcing a uniform ABC would create Liskov violations. Each provider's OAuth lives in its own `oauth_<name>.py`.

**Files touched:** `apps/api/src/munim/shared/crypto.py` (+ tests), `apps/api/src/munim/modules/connectors/oauth_shopify.py` (+ tests), `apps/api/src/munim/modules/connectors/{service,router,schemas}.py`, `apps/api/src/munim/connectors/{base.py,shopify/{client,connector}.py}` (+ tests), `apps/api/src/munim/shared/{config,constants}.py`, `apps/api/pyproject.toml` (cryptography + respx), `apps/web/src/modules/connectors/{components/*,hooks/*,api/*,types/*}.ts`.

**Reverts cleanly?:** yes — drop the new files, revert the modified ones. Demo flow still works.

---

## 2026-05-14 — Phase 3: connectors API + records API + clickable demo UI

**What changed:** Added two new vertical-slice backend modules — `connectors` (list/connect/sync endpoints) and `records` (list/detail) — plus `ConnectorRegistry` so adding Meta Ads / Shiprocket in Phase 4 is one registry entry. Moved the Shopify demo fixture from `tests/fixtures/` to `apps/api/data/fixtures/shopify/` (production demo path). Frontend gained `react-router-dom`, an `AppShell` with nav, and two new vertical-slice modules — `connectors` (Connect / Sync UI per card) and `records` (table + drawer showing raw + normalized side by side). The demo is now clickable: Connect → Sync → Records → row → see provenance.

**Files touched:** `apps/api/src/munim/connectors/registry.py`, `apps/api/src/munim/modules/connectors/*`, `apps/api/src/munim/modules/records/*`, `apps/api/data/fixtures/shopify/orders.json`, `apps/web/src/router.tsx`, `apps/web/src/pages/*`, `apps/web/src/modules/connectors/*`, `apps/web/src/modules/records/*`, `apps/web/src/shared/components/*`.

**Reverts cleanly?:** yes — the new modules can be deleted; revert the fixture move + `main.py` router registration + `main.tsx` to drop the phase.

---

## 2026-05-13 — Phase 2: universal schema + Shopify connector (demo mode)

**What changed:** Added the 4 SQLModel tables (`merchant`, `connector_credentials`, `record`, `run_log`) and the canonical `Order` Pydantic shape under `apps/api/src/munim/schemas/`. Added the connector abstraction in `apps/api/src/munim/connectors/base.py`: `Credential`, `SyncContext`, `SyncResult`, `BaseConnector` ABC, and `RowSink` — the only writer to the `record` table, which stamps provenance and upserts on `(merchant_id, source_system, source_id)`. Wired the first concrete connector, `ShopifyConnector`, with a demo iterator that reads a frozen `orders.json` fixture (3 orders covering COD / prepaid / partial). End-to-end integration tests prove the source-API → mapper → RowSink → `record` flow.

**Verified:** all 35 tests pass. `init_db()` seeds the default merchant and creates every table. Tables confirmed: `['connector_credentials', 'merchant', 'record', 'run_log']`.

**Files touched:**
- `apps/api/src/munim/schemas/order.py` (+ `__init__.py`, tests).
- `apps/api/src/munim/models/{merchant,connector_credentials,record,run_log}.py` (+ `__init__.py`, tests).
- `apps/api/src/munim/connectors/{base.py,_row_sink.py}` (+ tests).
- `apps/api/src/munim/connectors/shopify/{client,mapper,connector}.py` (+ fixtures, tests).
- `apps/api/src/munim/shared/{constants.py,db.py}` (expanded enums; init_db imports models + seeds merchant).
- `apps/api/conftest.py` (added `session` fixture).

**Reverts cleanly?:** yes — the new `models/` and `connectors/` packages can be deleted entirely; `shared/constants.py` and `shared/db.py` revert to their Phase 1 form.

---

## 2026-05-13 — Phase 1: monorepo + backend foundations + frontend scaffold + /health end-to-end

**What changed:** Bootstrapped the full monorepo. Backend (`apps/api`) ships a FastAPI app with the shared foundations — Pydantic Settings config (fail-fast on missing required env), structlog-based JSON logger, trace_id middleware (ULID-based, propagated via structlog contextvars + `X-Trace-Id` header), domain error classes + global exception handlers covering `MunimError`, `RequestValidationError`, `StarletteHTTPException`, and unhandled `Exception` (each returning the standard error envelope), SQLite engine/session with lazy `lru_cache` for testability, and the universal `SuccessEnvelope[T]` / `ErrorEnvelope` shapes. One module (`health`) ships end-to-end as a tracer for the foundations, with 6 tests covering success envelope, header echo, inbound trace preservation, invalid-trace rejection, unhandled-exception → 500 envelope, and typed `MunimError` → custom envelope.

Frontend (`apps/web`) ships Vite 6 + React 19 + Tailwind v4 (CSS-variable theming for light + dark via `@theme inline`), Zustand-backed theme store with `prefers-color-scheme` integration, ky-backed API client with Zod boundary validation that unwraps the envelope and throws typed `ApiError` / `ContractMismatchError`, TanStack Query client with retry policy that respects 4xx and contract mismatches, plus a fully wired `HealthSection` (connector) + `HealthCard` (dumb) pair that hits `/health` and renders status + version + trace_id.

Dev infra: ruff + mypy + pytest run green on backend; eslint + tsc + Vite build run green on frontend. Pre-commit hooks for ruff (check + format) + mypy + standard pre-commit-hooks, all via `language: system` so they re-use the uv-managed venv. GitHub Actions workflow runs the same checks on every push/PR. `docker-compose.yml` runs the api container (frontend stays on host in dev for HMR speed; see file header for reasoning).

**Live verification:** `curl http://127.0.0.1:8001/health` returned `{"success":true,"data":{"status":"ok","version":"0.1.0"},"trace_id":"tr_01KRH3H1NGGXQ15NVD261G7XGY"}` with matching `X-Trace-Id` header. A 404 returned `{"success":false,"error":{"code":"http.404","message":"Not Found","details":null},"trace_id":"tr_..."}`. JSON logs included `app.startup.beginning`, `app.startup.completed`, `health.checked` events with trace_id auto-bound.

**Decision: Vite + React 19 instead of Next.js 15.** The original plan in `docs/architecture.md` called for Next.js. Reversed at the start of Phase 1 build because the app is a single-page admin UI (no SSR, no SEO, no edge runtime concerns), Vercel AI SDK 5 is framework-agnostic so `useChat` works in Vite, and Vite's HMR + ~700ms build materially helps a 4-day clock. `docs/architecture.md` §2 updated in this commit to reflect the swap with reasoning.

**Two paid lessons (now in context.md → Problems & solutions):**
1. `ruff` N818 wants all exception classes to end in `Error`. Renamed `ValidationFailed` → `ValidationFailedError`. Followup convention: every domain error class in `shared/errors.py` ends in `Error`.
2. On Windows, `tempfile.TemporaryDirectory()` cannot delete a SQLite file while SQLAlchemy still holds it. Fix: dispose the engine in the pytest fixture's `finally` before TempDir cleanup. Test conftest now does this; documented in `apps/api/conftest.py`.

**Files touched (load-bearing):**
- Root: `.gitignore`, `.env.example`, `.editorconfig`, `.python-version`, `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `docker-compose.yml`.
- Backend: `apps/api/pyproject.toml`, `apps/api/conftest.py`, `apps/api/Dockerfile`, `apps/api/src/munim/main.py`, all of `apps/api/src/munim/shared/`, `apps/api/src/munim/modules/health/`.
- Frontend: `apps/web/package.json`, `apps/web/vite.config.ts`, `apps/web/tsconfig*.json`, `apps/web/eslint.config.js`, `apps/web/prettier.config.js`, `apps/web/index.html`, `apps/web/src/main.tsx`, `apps/web/src/app.tsx`, `apps/web/src/styles/globals.css`, all of `apps/web/src/shared/`, all of `apps/web/src/modules/health/`.
- Docs: `docs/architecture.md` (Vite swap reasoning in §2, §13, §15).

**Reverts cleanly?:** yes — the whole monorepo skeleton can be wiped without affecting anything except the docs in `docs/` (which predate this commit).

---

## 2026-05-13 — pre-build setup: conventions, CLAUDE.md, context, changelog

**What changed:** Added `docs/conventions.md` (the full rulebook), `CLAUDE.md` (the auto-loaded short version + module workflow), `CHANGELOG.md` (this file), and `context.md` (running log of work + problems + solutions).
**Why:** User-requested pre-build governance setup. Establishes the discipline (vertical slice, trace_id, no silent fallbacks, no magic strings, citation contract fail-closed, Decimal/UTC, Conventional Commits, subagent-driven module workflow) before any code is written. Designed to make the WHY of every code decision visible to assignment reviewers, per `docs/the-build.docx` scoring criteria.
**Files touched:** `docs/conventions.md`, `CLAUDE.md`, `CHANGELOG.md`, `context.md`.
**Reverts cleanly?:** yes — pure docs, no code dependencies yet.
