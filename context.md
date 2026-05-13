# Context

> The running log of this build. **Read this at the start of every session.** Update it whenever something non-trivial happens — a decision, a problem, a fix, a state change.
>
> The most important section is **Problems & solutions**. Every entry there is a paid lesson; never pay for it twice.

---

## Now

Phase 2 complete. Universal schema + RowSink + ShopifyConnector demo sync working end-to-end. All checks green:
- Backend: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` — all pass (35/35 tests).
- Tables: `['connector_credentials', 'merchant', 'record', 'run_log']` created by `init_db()`, default merchant seeded.
- Demo sync: `ShopifyConnector.sync_full()` reads frozen `orders.json`, maps 3 orders (COD/prepaid/partial) to `Order` Pydantic, writes to `record` table with full provenance. Second run is idempotent (0 upserts, 3 skipped).

**Next:** Phase 3 — API endpoints to trigger the sync + connector management UI + real OAuth scaffold.

---

## Done

- 2026-05-13 — `docs/the-build.docx` parsed and understood (the assignment brief).
- 2026-05-13 — `docs/requirements.md`, `docs/architecture.md`, `docs/research.md` written (pre-existing in repo, refined this session).
- 2026-05-13 — Governance setup: `docs/conventions.md`, `CLAUDE.md`, `CHANGELOG.md`, `context.md` (this file).
- 2026-05-13 — **Phase 1 complete.** Monorepo skeleton, backend foundations (config, logging, trace, errors, responses, db, constants), `/health` module with 6 tests, frontend scaffold (Vite + React 19 + Tailwind v4 + theme), shared API client (ky + Zod envelope unwrap), Zustand theme store, TanStack Query client, dumb `HealthCard` + connector `HealthSection`. Dev infra: pre-commit, GitHub Actions CI, `docker-compose.yml`. End-to-end live-verified. See `CHANGELOG.md` 2026-05-13 entry for details.
- 2026-05-13 — **Phase 2 complete.** Universal 4-table schema (`merchant`, `connector_credentials`, `record`, `run_log`), `Order` Pydantic (canonical normalized shape), `BaseConnector` ABC + `RowSink` writer, `ShopifyConnector` demo sync end-to-end. 35 tests, all green. See `CHANGELOG.md` 2026-05-13 Phase 2 entry for details.

---

## Next

1. **Phase 3 — API endpoints + demo UI + real OAuth scaffold.** Wire `/api/connectors/` endpoints to trigger `ShopifyConnector.sync_full`, build connector management UI, add real OAuth flow stub, add `RunLog` writes from the sync endpoint.
2. **Phase 4 — Connectors 2 and 3.** Meta Ads + Shiprocket, same pattern, fewer surprises.
3. **Phase 4 — Chat tools over the schema.** `query_orders`, `query_shipments`, `query_ad_spend`, `compute_metric`, `propose_action`. Tool return shape with `RowCitation`s.
4. **Phase 5 — Citation contract.** PydanticAI integration, system prompt, structured `GroundedAnswer` output, fail-closed post-processor for uncited numbers.
5. **Phase 6 — RTO Risk Mitigator agent.** APScheduler cron + signal extraction + scoring + `run_log` writes. No side effects.
6. **Phase 7 — Frontend modules.** Connectors page, chat page (streaming), agent runs page.
7. **Phase 8 — Demo seed data + `docker-compose up` story.**
8. **Phase 9 — README rewrite** (the deliverable's headline artifact).

Ranking re-evaluated at the start of each new phase.

---

## Problems & solutions

Every entry is a paid lesson. Read at the start of every session. Never repeat one.

### 2026-05-13 — `ruff` N818 requires exception class names to end in `Error`

**Problem:** `uv run ruff check src` failed with `N818 Exception name 'ValidationFailed' should be named with an Error suffix`.

**Root cause:** `ruff`'s pep8-naming rule N818 enforces the convention that exception classes end in `Error`. `MunimError` was fine; `ValidationFailed` (subclass) was not.

**Solution:** Renamed `ValidationFailed` → `ValidationFailedError` in `apps/api/src/munim/shared/errors.py`. Kept N818 enabled in `pyproject.toml` so future violations are caught.

**Guardrail:** Every domain-error subclass in `shared/errors.py` ends in `Error`. New pattern: `ConnectorRateLimitedError`, `LLMUnavailableError`, etc. Not `ConnectorRateLimited`, etc.

### 2026-05-13 (Phase 2) — `TYPE_CHECKING` guard + mypy `import-untyped` error when module doesn't exist yet (TDD forward-reference)

**Problem:** `base.py` in Task 4 needed to type-annotate `SyncContext.row_sink` as `RowSink`, but `_row_sink.py` didn't exist until Task 5. Using `TYPE_CHECKING` + `from munim.connectors._row_sink import RowSink` caused mypy to emit `import-untyped` because it found the package but not the specific module. Using a plain string `"RowSink"` caused ruff F821. Adding both `# noqa: F821` and `# type: ignore[name-defined]` on the same line fixed both.

**Root cause:** At Task 4, `munim.connectors` package exists (we created `__init__.py`) but `_row_sink.py` doesn't. Mypy differentiates "module not found" from "module found but untyped" — the latter still errors even with `TYPE_CHECKING`.

**Solution:** Use string annotation `"RowSink"` with dual suppression `# type: ignore[name-defined]  # noqa: F821`. Once Task 5 creates `_row_sink.py`, rewrite `base.py` to use `TYPE_CHECKING` cleanly — the import resolves, suppressions removed.

**Guardrail:** When TDD creates an ABC before its dependencies exist, use string annotations + dual suppress as a temporary bridge. Always clean up the suppress in the task that creates the dependency.

### 2026-05-13 — Windows: `tempfile.TemporaryDirectory()` cannot delete a SQLite file while the engine still holds it

**Problem:** Pytest fixture used `TemporaryDirectory()` to give each test a fresh SQLite. The tests passed, but teardown raised `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process` on `test.sqlite`. 4 of 6 tests reported as ERROR despite the assertions all running correctly.

**Root cause:** SQLAlchemy's engine pool keeps SQLite connections alive past the request lifecycle. On Linux/macOS the file is deleted via `unlink` regardless of open handles; on Windows, the OS refuses to delete an open file. So `TemporaryDirectory.__exit__` raises before the test can be marked passed.

**Solution:** In `apps/api/conftest.py`, wrap the fixture body in `try / finally`, and call `get_engine().dispose()` in the `finally` before `TemporaryDirectory` exits. Also clear the `lru_cache` so the next test gets a fresh engine.

**Guardrail:** Any new fixture that creates a temp-file DB on Windows MUST dispose the engine before tempdir cleanup. Documented in `apps/api/conftest.py` docstring.

---

## Decisions

Non-obvious choices made during the build. Different from `CHANGELOG.md` (mechanical: what changed). This is judgmental: why we picked X over Y.

### 2026-05-13 — Vite + React 19 instead of Next.js 15 for the frontend

**Decision:** Flipped the frontend stack from Next.js 15 (in original `docs/architecture.md`) to Vite 6 + React 19 at the start of Phase 1 build.

**Why:** The app is a single-page admin UI for an Indian D2C founder. No SSR need, no SEO concern, no edge-runtime story to justify Next's footprint. Vercel AI SDK 5 is framework-agnostic — `useChat` works in Vite. Vite's HMR (sub-second) and production build (~700ms at current size) materially help on a 4-day clock.

**Revisit if:** we decide to ship a marketing landing page, or if we adopt a SSR-only feature like dynamic OG images for shareable agent runs. Neither is in scope.

`docs/architecture.md` §2, §13, §15 updated to reflect the swap. Tracked in `CHANGELOG.md` 2026-05-13.

### 2026-05-13 — Frontend Docker is for prod only, dev runs on host

**Decision:** `docker-compose.yml` includes only the `api` service. Frontend dev runs on the host via `pnpm --filter @munim/web dev`; Vite proxies `/api/*` to `localhost:8000`.

**Why:** Dockerising Vite slows HMR (volume mounts on Windows are particularly painful), and brings nothing demo-relevant — the API container is what reviewers need to see boot deterministically. A static-build + nginx production image lands when we ship a deployable image, not before.

**Revisit if:** the reviewer experience requires `docker-compose up` to also boot the frontend. We can ship a prod-mode `web` service (Vite build → nginx serve) without changing dev workflow.

### 2026-05-13 — no new project-specific skill; lean on existing superpowers

**Decision:** Did not create a custom skill for the module-build workflow. Codified the workflow in `CLAUDE.md` and pointed at existing superpowers skills (`writing-plans`, `subagent-driven-development`, `requesting-code-review`, `verification-before-completion`, `test-driven-development`).

**Why:** `superpowers:writing-skills` explicitly says project-specific conventions belong in `CLAUDE.md`, not skills. Existing superpowers already cover every step of the workflow. Creating a new skill correctly would have required RED/GREEN/REFACTOR pressure-testing — significant overhead on a 4-day deadline for no net new capability.

**Revisit if:** we notice the existing skills missing a step we keep manually re-doing.

### 2026-05-13 — single flat `context.md` and `CHANGELOG.md` at repo root

**Decision:** One file each, both at the repo root, append-only, newest at top for `CHANGELOG`.

**Why:** Simpler. Grep-friendly. No per-session rotation to maintain. User's call.

**Revisit if:** files grow past ~5000 lines (unlikely within this build).

### 2026-05-13 — Phase 1 included a working `/health` endpoint as a tracer, not just dead foundations

**Decision:** Phase 1 shipped end-to-end-working `/health` (backend service + tests + frontend hook + dumb component) rather than just shared utilities.

**Why:** Untested foundations rot silently. A tracer endpoint forces the envelope shape, trace_id wiring, JSON logging, error handlers, and the frontend ↔ backend boundary to ALL be exercised. Catching the N818 lint rule and the Windows tempdir bug at Phase 1 saves them from biting in Phase 4.

### 2026-05-13 — Phase 2 test counts differ from plan estimates (35 actual vs 26 planned)

**Decision:** Followed the plan's test code exactly; did not add or remove tests. The plan's per-task "Expected: N passed" counts were estimates that didn't match the actual test functions written. Final count: 6 health + 5 order + 5 tables + 6 row_sink + 1 client + 8 mapper + 4 connector = 35. All 35 test functions directly from the plan; no extras added. The plan's §13.4 filter was already applied by the plan author.

**Why the counts were off:** The plan said Task 5 would produce 4 RowSink tests but wrote 6 (`test_row_sink_hash_is_canonical`, `test_row_sink_preserves_raw_payload_verbatim`, and 4 CRUD tests). Task 8 planned 6 mapper tests but wrote 8. Task 9 planned 3 connector tests but wrote 4 (included `test_shopify_sync_preserves_raw_payload_verbatim`). These are all meaningful per §13.4.

### 2026-05-13 — uv resolved Python 3.14 instead of 3.11 on this machine

**Decision:** uv chose Python 3.14 to satisfy `requires-python = ">=3.11"` (probably the newest available on the machine). Left it as-is; code is 3.11+ compatible.

**Why:** Pinning a Python version with `requires-python = "==3.11.*"` would force a download, slow startup, and provides no measurable benefit. The `.python-version` file is `3.11` (the minimum we test against); uv uses it as a floor.

**Revisit if:** we hit a 3.14-only behavior that breaks 3.11 CI. None observed in Phase 1.

---

## AI tool usage (for the README's honesty section)

Tracked here as we go, summarised in the README at the end.

- 2026-05-13 — Pre-build governance docs (`docs/conventions.md`, `CLAUDE.md`, `CHANGELOG.md`, this file): drafted by Claude (Opus 4.7) in this session, based on the user's spoken guidelines + the existing `docs/` foundation. User reviewed and iterated on the guideline list before writing started; structure and rule-set is collaborative, prose is Claude's.
- 2026-05-13 — Phase 1 implementation (backend foundations, frontend scaffold, infra, `/health` tracer): generated by Claude in this session under direct user instruction. The user approved the scope; Claude wrote the code without dispatching a subagent (user's explicit override of the standard workflow — Phase 1 was mechanical scaffolding). Bugs surfaced + fixed in-session: N818 lint, Windows tempdir cleanup, Vite TS inference on the API client, missing `@types/node`.
- 2026-05-13 — Phase 2 implementation (universal schema, RowSink, ShopifyConnector): executed by Claude Sonnet 4.6 as a coder subagent dispatched per the `superpowers:subagent-driven-development` workflow. Followed plan top-to-bottom, TDD per task. Issues surfaced + resolved in-session: ruff F821 + mypy name-defined for forward-reference RowSink in Task 4 (dual-suppress bridge, cleaned up in Task 5); ruff I001 import sort in test_tables.py (auto-fixed); mypy `dict` → `dict[str, Any]` in test_order.py; ruff RUF059 unused unpacked variable (prefixed with `_`); ruff I001 + format in test_mapper.py (typed fixture annotation).
