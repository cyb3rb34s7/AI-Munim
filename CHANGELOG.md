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
