# Conventions

> The rulebook. Every commit in this repo follows these. If a convention has no `Why`, it has no force — every rule here is justified, because every rule here will be questioned at some point during the build.

If something here is wrong or stale, fix the convention first, then the code. The convention file is the source of truth, not whatever happens to be in the repo right now.

---

## 0. Reading order before any work

Every time work starts in this repo — every new session, every new module, every "let's pick this up again" — read these three files first, in this order:

1. `context.md` — running log of what's done, what's in progress, problems faced, solutions applied. **Never repeat a mistake that's already in here.**
2. `CHANGELOG.md` — what changed and why, dated. Use this when reverting or tracing regressions.
3. `docs/conventions.md` — this file.

Then read whatever else the task needs (`docs/requirements.md`, `docs/architecture.md`, the relevant module).

**Why:** The cost of re-reading is seconds. The cost of redoing a mistake we already solved is hours, and it's the most demoralising kind of waste.

---

## 1. Core principles (in order of priority)

1. **KISS.** The simplest thing that satisfies the requirement, written so the next reader can hold it in their head.
2. **DRY, but only after the third occurrence.** First time: write it. Second time: notice. Third time: extract. Don't pre-abstract.
3. **No silent fallbacks.** If a code path can fail, it fails loudly. If we need a fallback, it gets called out explicitly in the PR and in `CHANGELOG.md`.
4. **Fail-closed.** When in doubt, reject the operation. Never ship an unverified number, never silently swallow a failed sync, never hide an exception.
5. **Trace everything.** Every request, every tool call, every agent run gets a `trace_id` that follows it through logs, DB, and outputs.
6. **Provenance on every row.** No data lives in the system without a source. No number reaches the user without a citation.
7. **Honesty over polish.** Known gaps are documented in `context.md` and the README. We list what breaks before anyone has to ask.

---

## 2. Process discipline

### 2.1 Module workflow (every feature follows this)

| Step | Who | Output |
|---|---|---|
| 1. Define the module | Me + user, in conversation | Acceptance criteria for this slice |
| 2. Write the plan | Me, using `superpowers:writing-plans` | Plan document inline in chat |
| 3. Review and iterate | User | Approved plan |
| 4. Implement | Coder subagent (dispatched by me, given `docs/conventions.md` + plan) | Code + tests, committed |
| 5. Critical code review | Reviewer subagent (dispatched by me, given diff + `docs/conventions.md`) | Review report with issues ranked by severity |
| 6. Apply fixes | Coder subagent or me, depending on scope | Updated code |
| 7. Update docs | Me | `context.md` + `CHANGELOG.md` updated, **then committed in the same commit** |
| 8. Manual verification | User | Pass / send back |

Steps 1–3 can iterate before any code is written. Step 5 is non-optional; we always run it. Step 7 is non-optional; if `context.md` and `CHANGELOG.md` don't reflect the change, the change isn't done.

### 2.2 `context.md`

Single flat file at repo root. Append-only. Sections it must contain at all times:

- **Now** — what is in progress right now.
- **Done** — what is complete, with one-line entries dated.
- **Next** — the queue, ranked.
- **Problems & solutions** — dated entries: problem, root cause, solution, follow-up. **This is the most important section.** Read it at the start of every session. Never repeat one of these.
- **Decisions** — non-obvious decisions taken during the build, with reasoning. Different from `CHANGELOG.md` (which is mechanical: what changed). This is judgmental: why we picked X over Y.

### 2.3 `CHANGELOG.md`

Single flat file at repo root. Append-only, newest at top. Format per entry:

```
## YYYY-MM-DD — short title

**What changed:** one-line summary of the diff.
**Why:** the actual reason, traceable to a requirement, a problem in context.md, or a user request.
**Files touched:** key files. Not exhaustive; just the load-bearing ones.
**Reverts cleanly?:** yes / no / partially (with reason).
```

**Why:** When something breaks, the first question is "what did we change recently?" The changelog answers that in seconds; `git log` answers it in minutes.

### 2.4 Conventional Commits

Commit message format:

```
<type>(<scope>): <subject>

<body — optional>
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `ci`. Scope is the module (`orders`, `chat`, `connectors/shopify`, etc.).

Examples:
- `feat(connectors/shopify): implement sync_full with cursor pagination`
- `fix(chat): citation enforcer was passing decimal commas as numbers`
- `docs(conventions): clarify error envelope code field`

**Why:** Reviewers of this assignment will read commit history. Conventional commits make speed and care visible.

### 2.5 Pre-commit hooks

Before any commit lands, locally:

- **Python:** `ruff check --fix`, `ruff format`, `mypy`
- **TypeScript:** `eslint --fix`, `prettier --write`, `tsc --noEmit`
- **Both:** unit tests for the touched module pass

If a hook fails, fix the cause. Do not bypass with `--no-verify`.

---

## 3. Architecture: vertical slice

Each module owns everything it needs — schemas, business logic, API endpoints, UI components, hooks, tests — in one folder. Cross-module sharing goes through explicit `shared/` folders, not through reach-in.

### 3.1 Backend structure

```
apps/api/src/munim/
  modules/
    <module-name>/                # e.g., orders, chat, agent_runs
      __init__.py
      router.py                   # FastAPI routes for this module
      service.py                  # business logic (called by router)
      repository.py               # DB access (called by service)
      schemas.py                  # Pydantic request/response models for this module
      constants.py                # module-specific enums
      tests/
        test_service.py
        test_router.py
        fixtures.py
  shared/
    db.py                         # engine, session
    logging.py                    # JSON logger setup
    trace.py                      # trace_id contextvar + middleware
    errors.py                     # domain error base classes + global handler
    config.py                     # Pydantic Settings, fail-fast validation
    responses.py                  # success/error envelope builders
    constants.py                  # cross-module enums
  connectors/
    base.py                       # BaseConnector ABC
    <connector-name>/
      connector.py
      mapper.py                   # source payload -> Pydantic normalized
      tests/
  agents/
    <agent-name>/
      agent.py
      signals.py                  # signal extractors
      tests/
  main.py                         # FastAPI app composition
```

**Rules:**
- A module's `router.py` calls only its own `service.py`. Services can call shared utilities and other modules' services, but never another module's router or repository directly.
- Pydantic schemas for cross-cutting entities (`Order`, `Shipment`, etc., per `docs/architecture.md §4.2`) live in a top-level `apps/api/src/munim/schemas/` directory because they are the universal contract. Module-specific request/response shapes stay inside the module.

### 3.2 Frontend structure

```
apps/web/src/
  modules/
    <module-name>/                # e.g., chat, connectors, agent-runs
      api/                        # ky calls for this module
      components/                 # dumb components: receive props, render
      hooks/                      # all logic lives here
      store/                      # zustand slice if module needs ephemeral UI state
      types/                      # module-specific types
      utils/                      # module-specific pure functions
      constants.ts                # module-specific enums
      index.ts                    # public surface of the module
  shared/
    components/                   # Button, Modal, Dialog, Loader, Badge, etc.
    hooks/                        # cross-cutting hooks
    api/
      client.ts                   # ky instance + envelope unwrap + global error
      errors.ts                   # error class hierarchy mirroring backend codes
    store/                        # app-level zustand stores (theme, etc.)
    utils/                        # inr, fmtIST, etc.
    types/                        # generated from backend Pydantic
    constants/                    # cross-module enums (mirrors backend constants)
    theme/                        # tailwind tokens, theme provider
  app/                            # Next.js App Router pages — thin, compose module surfaces
  styles/
    globals.css
```

**Rules:**
- `app/` pages do not contain business logic. They import a module's public surface (`modules/chat/index.ts`) and arrange it.
- A module exports through `index.ts`. Other modules import only from that public surface, never from internals.

### 3.3 The "share when third time" rule

A util or component moves to `shared/` only after a third independent use. Before that, copy. **Why:** Premature abstraction is more painful than duplication at small scale, and refactoring at the third occurrence is when the right shape is finally visible.

---

## 4. API contract

### 4.1 Response envelope (success)

```json
{
  "success": true,
  "data": { /* whatever the endpoint returns */ },
  "trace_id": "tr_01JABCDXYZ..."
}
```

### 4.2 Response envelope (error)

```json
{
  "success": false,
  "error": {
    "code": "validation.missing_field",
    "message": "Human-readable message safe to show to a user.",
    "details": { /* optional structured diagnostic data */ }
  },
  "trace_id": "tr_01JABCDXYZ..."
}
```

**Rules:**
- Every response has `trace_id`. Including errors. Including 500s.
- `success` is a boolean discriminator. Frontend branches on it.
- Errors **always** have a `code`. UI logic branches on `code`, never on `message`. Messages are display copy.
- `details` is optional structured data — e.g., for validation errors, the list of failing fields. Never put PII or secrets here.
- Status codes: 2xx for success, 4xx for caller fault, 5xx for our fault. The envelope shape is identical regardless.

### 4.3 Error code namespacing

`<domain>.<reason>`:

- `auth.invalid_token`, `auth.expired_token`, `auth.missing_credentials`
- `validation.missing_field`, `validation.bad_format`, `validation.out_of_range`
- `connector.rate_limited`, `connector.upstream_unavailable`, `connector.auth_failed`
- `chat.unverified_number`, `chat.citation_invalid`, `chat.retry_exhausted`
- `agent.run_in_progress`, `agent.data_sparse`
- `system.unexpected`, `system.database_unavailable`, `system.llm_unavailable`

The full registry lives in `apps/api/src/munim/shared/errors.py` as a `StrEnum` and is mirrored to the frontend as an `as const` union.

### 4.4 Pagination

Cursor-based for record streams:

```json
{
  "success": true,
  "data": { "items": [...], "next_cursor": "..." | null },
  "trace_id": "..."
}
```

No `page`/`limit`. **Why:** cursor-based survives concurrent writes; offset pagination doesn't.

### 4.5 Idempotency

Any `POST` that creates data accepts an `Idempotency-Key` header. Server stores the response keyed by `(merchant_id, idempotency_key)` for 24h and returns the same response on retry. Required for connector sync triggers and any future write side-effect.

---

## 5. Trace IDs

### 5.1 Generation

- Generated at the edge (FastAPI middleware) for any inbound HTTP request.
- Generated at the trigger for any cron-driven agent run (APScheduler tick).
- Format: `tr_<ULID>` (sortable by time, URL-safe, 26 chars).
- Stored in a `contextvars.ContextVar` so it's accessible from any function in the same async task without threading it through arguments.

### 5.2 Propagation

- Every outbound HTTP call (to Shopify, Meta, Shiprocket, the LLM) sends `X-Trace-Id: tr_...` as a header.
- Every DB write that produces a `run_log` row stores `trace_id` in `detail_json`.
- Every LLM tool call result includes `trace_id` in its `ToolResult.data` (not as a citation; as a diagnostic field).
- Frontend reads `trace_id` from the response envelope and tags any subsequent retry or follow-up call with the same id.

### 5.3 Logging

Every log line is JSON with these mandatory fields:

```json
{
  "ts": "2026-05-13T10:42:31.918Z",
  "level": "info",
  "event": "connector.sync.completed",
  "trace_id": "tr_...",
  "merchant_id": "m_...",
  "latency_ms": 1234,
  "...event-specific fields..."
}
```

**Rules:**
- `event` follows dot notation: `<area>.<action>.<state>`. E.g., `chat.tool.invoked`, `connector.sync.failed`, `agent.run.finished`.
- No `print()`. No `console.log()`. Only the structured logger.
- Secrets, tokens, full raw payloads — never in logs. Provenance lives in DB; logs reference `record.id`.

---

## 6. Type safety end-to-end

### 6.1 Backend source of truth

Pydantic models in `apps/api/src/munim/schemas/` define the canonical entity shapes. Module-specific request/response shapes live in the module's `schemas.py`.

### 6.2 Frontend mirror

Generate TypeScript types from the FastAPI OpenAPI schema using `openapi-typescript` (or hand-mirror if generation is finicky), output to `apps/web/src/shared/types/api.ts`. Frontend imports from there.

### 6.3 Boundary validation

The frontend API client (`shared/api/client.ts`) parses every response through Zod **before** returning to the caller. If parsing fails, throw a typed `ContractMismatchError` — never a generic JSON object reaches a component.

**Why:** The Pydantic ↔ TS boundary is the single most common place for silent drift. Boundary validation catches it on the first request, not when a component crashes three screens later.

---

## 7. Constants and enums

**No magic strings in critical comparisons. Ever.**

### 7.1 Backend

```python
# apps/api/src/munim/shared/constants.py
from enum import StrEnum

class PaymentMethod(StrEnum):
    COD = "cod"
    PREPAID = "prepaid"
    PARTIAL = "partial"

class EntityType(StrEnum):
    ORDER = "order"
    SHIPMENT = "shipment"
    AD_SPEND = "ad_spend"
    # ...

class ShipmentStatus(StrEnum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RTO = "rto"
    # ...
```

Comparisons use the enum: `if order.payment_method is PaymentMethod.COD:`. Never `if order.payment_method == "cod":`.

### 7.2 Frontend

```ts
// apps/web/src/shared/constants/payment.ts
export const PaymentMethod = {
  COD: "cod",
  PREPAID: "prepaid",
  PARTIAL: "partial",
} as const;
export type PaymentMethod = (typeof PaymentMethod)[keyof typeof PaymentMethod];
```

Same names as backend. **The two definitions are mirrored manually until codegen is wired up; CI will assert they match.**

### 7.3 What counts as "critical"

Anything used in a comparison, switch, or branch. Display-only labels can be literals (they go through the i18n / copy layer anyway).

---

## 8. Money and time

### 8.1 Money

- **Backend:** `decimal.Decimal` everywhere a rupee value exists. Serialized as a string (`"1234.56"`), never a float. Validated by Pydantic with `Decimal` field type.
- **Frontend:** numbers are strings on the wire; convert to `bignumber.js` or `decimal.js` only if arithmetic is needed. For display, one helper:

```ts
// apps/web/src/shared/utils/inr.ts
export const inr = (value: string | number): string => /* ... */;
// Usage: inr("1234.56") -> "₹1,234.56"
```

- **DB:** `Decimal` is stored as a string in the `normalized` JSON. SQLite has no native decimal — string is correct.
- **Floats never touch a rupee value, anywhere, ever.**

### 8.2 Time

- **Wire format:** UTC ISO 8601 with `Z` suffix. `"2026-05-13T10:42:31.918Z"`.
- **DB storage:** UTC. `DateTime` columns store UTC; no timezone-aware shenanigans inside the DB.
- **Display:** convert to IST at the rendering boundary. One helper:

```ts
// apps/web/src/shared/utils/datetime.ts
export const fmtIST = (iso: string, fmt?: string): string => /* ... */;
```

- **Backend timestamps** use `datetime.now(timezone.utc)`. Never `datetime.now()` (which is naive).
- **Pincode is a string,** not an int. Leading zeros are real.

---

## 9. Configuration

`apps/api/src/munim/shared/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str          # required, no default
    openai_api_key: str        # required, no default
    anthropic_api_key: str     # required, no default
    shopify_client_id: str     # required, no default
    # ...
    log_level: str = "info"    # optional, defaults documented

    model_config = {"env_file": ".env", "extra": "forbid"}

settings = Settings()  # imports throw at startup if anything required is missing
```

**Rules:**
- Required env vars have **no default**. Missing config = startup failure with a named cause.
- `.env.example` is committed and kept in sync. PRs that add a required env var must update `.env.example`.
- `.env` is gitignored. No exceptions.
- Secrets never reach the frontend bundle. Anything the frontend needs goes through `NEXT_PUBLIC_*` and is non-sensitive.

---

## 10. Errors

### 10.1 Don't broad-catch

Forbidden:

```python
try:
    do_thing()
except Exception:
    pass  # or log and continue
```

Allowed:

```python
try:
    do_thing()
except RateLimitedError as e:
    raise ConnectorRateLimited(connector="shopify", retry_after=e.retry_after) from e
```

**Why:** A broad `except Exception` is a silent fallback. If you don't know what specific failure you're handling, you're not handling it — you're hiding it.

### 10.2 Domain error classes

`apps/api/src/munim/shared/errors.py`:

```python
class MunimError(Exception):
    code: str = "system.unexpected"
    http_status: int = 500

class ValidationFailed(MunimError):
    code = "validation.missing_field"
    http_status = 422

class ConnectorRateLimited(MunimError):
    code = "connector.rate_limited"
    http_status = 429
# ...
```

A single global FastAPI exception handler converts any `MunimError` into the standard error envelope using the class's `code` and `http_status`. Anything else bubbles up as `system.unexpected` with the stacktrace logged but **not** returned in the response.

### 10.3 Fallback policy

**No silent fallbacks.** If a code path could fall back to a default, halt the conversation and flag it:

- In code review: the reviewer subagent flags any new `try/except` that doesn't re-raise.
- In implementation: I (or the coder subagent) ask the user before writing a fallback. Never silently insert one.

If we agree a fallback is right (e.g., "if the user's pincode lookup fails, treat as risk score = neutral"), it goes in:
1. Code: with a structured log of the fallback hit, including `trace_id`.
2. `CHANGELOG.md`: as a deliberate decision with reasoning.
3. README: in the "where it breaks" section.

---

## 11. Backend specifics

### 11.1 FastAPI patterns

- Routers in `<module>/router.py`. Group by module.
- Dependencies via `Depends()` — DB session, current merchant, current user (placeholder for v0).
- Request/response models always declared with Pydantic; never `dict`.
- Streaming responses for chat use SSE with the Vercel AI SDK Data Stream Protocol shape.

### 11.2 DB access

- SQLModel (Pydantic + SQLAlchemy) as the ORM.
- Repositories own raw queries. Services call repositories.
- All queries are merchant-scoped — `WHERE merchant_id = ?` is non-optional, even with one merchant.
- JSON-path access (`normalized->>'placed_at'`) is acceptable; raw SQL goes in repositories only, never in services.

### 11.3 Tests location

Tests live next to the code: `modules/orders/tests/test_service.py`. Run with `uv run pytest`.

### 11.4 No DB mocking

Integration tests hit a real SQLite (a temp file per test). Mocks for the DB are forbidden. **Why:** mock-passes-but-prod-fails is exactly the class of bug we lose hours to.

External APIs (Shopify, Meta, Shiprocket) are recorded with VCR-style cassettes; the test runs offline against the recording.

---

## 12. Frontend specifics

### 12.1 Theme first

Tailwind v4 tokens (CSS variables) in `shared/theme/`. Light + dark. Defined before any component is built.

### 12.2 State separation

- **Server state:** TanStack Query. Cache, refetch, invalidation, optimistic updates.
- **UI state:** Zustand. Modal open/closed, theme, form drafts, ephemeral toggles.
- **Never put server data in Zustand.** TanStack already does it better.

### 12.3 API client

`shared/api/client.ts`:

- `ky` instance with base URL, default headers, retry policy.
- Outbound interceptor: attach `trace_id` (generated client-side for retries) if present.
- Inbound interceptor: parse envelope. If `success: true`, return `data` (Zod-validated). If `success: false`, throw a typed `ApiError` with `code`, `message`, `trace_id`.
- Components never see the envelope. Hooks call the client, components consume the hook.

### 12.4 Dumb components

A component:
- receives props,
- renders JSX,
- can hold local cosmetic state (open/closed),
- **cannot** call the API,
- **cannot** know about Zustand stores directly — it receives data and callbacks from a hook.

Logic — fetches, mutations, derived data, side effects — lives in hooks in `<module>/hooks/`.

### 12.5 Reusable UI primitives

Built once in `shared/components/`, reused everywhere:

- `Button`, `IconButton`
- `Modal`, `Dialog`, `Drawer`, `Popover`
- `Loader` (spinner + skeleton variants)
- `Badge` (used for citation badges in chat)
- `Toast`
- `EmptyState`
- `ErrorBoundary`

If a module is about to build its own `Modal`, it doesn't. It uses `shared/components/Modal`.

### 12.6 No magic strings in branches

Same rule as backend (§7). All status comparisons, view modes, and tab keys go through `as const` enums.

---

## 13. Testing

### 13.1 What we test

- Connector mappers: source payload → normalized Pydantic shape (frozen fixtures).
- Services: business logic with a real SQLite + seeded fixtures.
- Routers: integration tests with FastAPI `TestClient`.
- Citation enforcer: edge cases — uncited numbers, hallucinated row ids, paraphrase mismatches (the latter as `xfail` since v0 doesn't catch them).
- Agent: one scoring run against fixture orders, asserting `run_log` shape and zero side effects.
- Frontend: critical hooks (chat, citation rendering). Visual regression / e2e is out of scope for v0.

### 13.2 When we write tests

Alongside the implementation, in the same commit. Never "tests will follow in the next PR." If TDD fits the change, TDD. If a regression test is enough, write the regression test.

### 13.3 What "passes" means

`pytest -q` is green. `tsc --noEmit` is green. `ruff` and `eslint` are green. **No skipped tests without a `@pytest.mark.xfail(reason=...)` linking back to a `context.md` problem entry.**

### 13.4 Meaningful tests only

A test is meaningful when **its failure indicates a real bug**. Tests that pass forever unless someone deliberately breaks them, or whose failure mode is "I changed the assertion to match the new implementation," are noise — worse than no test, because they imply coverage that doesn't exist.

Before writing a test, articulate one sentence: **"this fails when X breaks"** where X is a real, harmful condition. If you can't, don't write the test.

**Write a test when:**
- It encodes an invariant a future change might accidentally violate (idempotency, ordering, provenance preservation).
- It tests a contract between components that typechecking can't catch (e.g., that a connector's mapped output is something the `RowSink` can store and round-trip).
- It tests an edge case with a known bug class — off-by-one, leading-zero strings, integer IDs becoming strings, missing optional fields, timezone offsets, partially-paid states.
- It tests a failure mode (raises the right typed error, returns the right code, fails closed).

**Don't write a test when:**
- It re-asserts a type the typechecker already enforces (e.g., `assert isinstance(x, Decimal)` on a field declared `Decimal`).
- It just stores and reads back, with no constraint, no invariant, no transformation.
- It mocks the function under test and asserts the mock was called.
- It re-implements the function's logic inside the assertion.
- Its failure could only be triggered by removing or rewriting the assertion itself.

**Smell test:** if a test would still pass after you replace its assertions with `pass`, the assertions don't matter — delete the test.

This is the user's hard-won lesson from prior projects: bloated test suites that give false confidence are worse than a smaller suite that catches real things. Apply the filter when writing the plan, and apply it again when the subagent (or anyone) writes the actual tests.

---

## 14. Quality gates

- CI on every push: lint, typecheck, tests.
- Pre-commit on local: same checks, faster subset.
- Reviewer subagent runs on every meaningful change before manual test.
- A change isn't done until `context.md` and `CHANGELOG.md` are updated **in the same commit** as the change.

---

## 15. AI tool usage disclosure

The brief asks for honesty about what we wrote vs. what an LLM wrote. We track this as we go:

- **`context.md` Decisions section** notes when an LLM (or this coding session) generated a non-trivial chunk vs. when it was hand-written.
- The README's "AI tools" section summarises that for the reviewer.

We don't apologise for using AI tools. We report it.

---

## 16. When this file is wrong

It will be. Update this file in the same PR as the code that proved it wrong. Note the change in `CHANGELOG.md` with type `docs(conventions)`. Don't quietly diverge.
