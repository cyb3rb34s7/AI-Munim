# Context

> The running log of this build. **Read this at the start of every session.** Update it whenever something non-trivial happens — a decision, a problem, a fix, a state change.
>
> The most important section is **Problems & solutions**. Every entry there is a paid lesson; never pay for it twice.

---

## Now

Phase 5 complete + review fixes + live OpenAI smoke. 135 backend tests green. Frontend chat page is Phase 6.
- pydantic-ai 1.96.0 installed; TestModel API confirmed (custom_output_args + call_tools=[...]).
- ToolReturnPart.content holds the raw Python return value — citation walk confirmed empirically.
- Enforcer regex (post-review): currency (₹/Rs./$) + percent + count+entity_noun + comma-thousands + Indian shortform (lakh/crore/cr). All branches allow optional leading minus ([-−]?) so stripped negatives don't leave a hanging sign. Currency uses strict \d{1,3}(?:,\d{3})* so sentence commas are preserved. used_citations cross-check now enforced. _PROXIMITY_CHARS=64.
- Reviewer surfaced 8 Important findings; all applied: greedy currency comma → strict, Unicode minus consumed, Indian-format branch, used_citations validation, _row_to_citation no-fallback, MetricFormula StrEnum, magic-string-in-test, structured logging + trace_id in run_log, narrow except in agent.
- **Live smoke (2026-05-14, real OpenAI gpt-4o-mini, real Shopify data):**
  - Q: "How many orders do I have, and what is the total revenue?"
  - A: "You have 3 orders[cite:1,2,3] with a total revenue of Rs.44.97[cite:1,2,3]." (math: 13.07 + 23.00 + 8.90 = 44.97 ✓)
  - Q: "Show me my orders shipping to Bengaluru pincode 560001."
  - A: "You have 1 order[cite:3] shipping to Bengaluru (pincode 560001) worth Rs.13.07[cite:3]." (pincode preserved as categorical, count + currency both cited)
- Final state: 135/135 tests, ruff + mypy clean, frontend untouched.

---

## Done

- 2026-05-13 — `docs/the-build.docx` parsed and understood (the assignment brief).
- 2026-05-13 — `docs/requirements.md`, `docs/architecture.md`, `docs/research.md` written (pre-existing in repo, refined this session).
- 2026-05-13 — Governance setup: `docs/conventions.md`, `CLAUDE.md`, `CHANGELOG.md`, `context.md` (this file).
- 2026-05-13 — **Phase 1 complete.** Monorepo skeleton, backend foundations (config, logging, trace, errors, responses, db, constants), `/health` module with 6 tests, frontend scaffold (Vite + React 19 + Tailwind v4 + theme), shared API client (ky + Zod envelope unwrap), Zustand theme store, TanStack Query client, dumb `HealthCard` + connector `HealthSection`. Dev infra: pre-commit, GitHub Actions CI, `docker-compose.yml`. End-to-end live-verified. See `CHANGELOG.md` 2026-05-13 entry for details.
- 2026-05-13 — **Phase 2 complete.** Universal 4-table schema (`merchant`, `connector_credentials`, `record`, `run_log`), `Order` Pydantic (canonical normalized shape), `BaseConnector` ABC + `RowSink` writer, `ShopifyConnector` demo sync end-to-end. Reviewer subagent surfaced 1 critical + 4 important findings (all time-handling + extra=forbid + magic string); all applied. 36 tests, all green. See `CHANGELOG.md` 2026-05-13 Phase 2 entry for details.
- 2026-05-14 — **Phase 3 complete.** Connectors + Records API, AppShell + nav, two new frontend modules. End-to-end demo working at `/connectors` and `/records`. Reviewer subagent surfaced 2 Important findings (ConnectorSyncError dead code + duplicated records query key); all applied + tests added. Live browser smoke (agent-browser) walked all 8 steps of the recipe — pass.
- 2026-05-14 — **Phase 4 complete.** Real OAuth + Admin API for Shopify. Reviewer surfaced 3 Important findings (typed decrypt error, shop-domain defense-in-depth, body truncation); all applied. 95 backend tests green. Live smoke against real Shopify dev store walked Connect → Sync → Records drawer with real Admin API data.
- 2026-05-14 — **Phase 5 complete.** Chat backend + citation contract, the scored axis of the brief. Reviewer surfaced 8 Important findings (regex greedy comma, Unicode minus, Indian-format, used_citations cross-check, silent fallback in _row_to_citation, magic strings, observability gaps, broad except); all applied. 135 backend tests green. Live smoke against real OpenAI gpt-4o-mini + real Shopify data: chat produces grounded answers with cite markers, math correct, pincode preserved, trace_id propagated.

---

## Next

1. **Phase 6 — Frontend chat page.** `useChat` hook, citation badges, `POST /chat/messages` wired, streaming optional.
2. **Phase 7 — RTO Risk Mitigator agent.** APScheduler cron + signal extraction + scoring + `run_log` writes. No side effects.
3. **Phase 8 — Frontend agent runs page.** Agent runs table, run detail.
4. **Phase 9 — Demo seed data + `docker-compose up` story + README rewrite** (the deliverable's headline artifact).
5. **Phase 10 — Meta Ads + Shiprocket connectors.** Same pattern as Shopify Phase 4.

Ranking re-evaluated at the start of each new phase.

---

## Problems & solutions

Every entry is a paid lesson. Read at the start of every session. Never repeat one.

### 2026-05-14 (Phase 5 live smoke) — pydantic-settings does not propagate values to os.environ; use python-dotenv as the canonical bridge

**Problem:** `OPENAI_API_KEY` was in `apps/api/.env` and Pydantic Settings loaded it into `settings.openai_api_key` correctly. But the first chat request returned `system.unexpected` because `openai.AsyncOpenAI()` reads `os.environ["OPENAI_API_KEY"]` directly, and pydantic-settings doesn't mirror .env values into `os.environ`.

**Root cause:** pydantic-settings reads `.env` via its own parser into the Settings instance; it doesn't touch `os.environ`. Third-party SDKs (OpenAI, Anthropic, anything that reads env vars) therefore never see .env values unless something else loads them.

**Solution:** Use `python-dotenv` as the canonical bridge. `load_dotenv(override=False)` in `main.py`'s `lifespan` populates `os.environ` from `.env`. Pydantic Settings still reads from `os.environ` (which now has the values), and third-party SDKs see them too. One library, one source of truth, no per-SDK hacks. `override=False` ensures pytest's `monkeypatch.setenv` still wins.

Initial fix was a manual `os.environ["OPENAI_API_KEY"] = settings.openai_api_key` bridge — user flagged that python-dotenv is the cleaner pattern; refactored.

**Guardrail:** Any project using pydantic-settings with third-party SDKs that read env directly should add `python-dotenv` and call `load_dotenv(override=False)` at startup. Don't do per-SDK env mirroring — it doesn't scale across providers.

### 2026-05-14 (Phase 5) — pydantic-ai 1.96.0 TestModel calls ALL tools by default, breaking agent tests

**Problem:** `TestModel(custom_output_args=canned)` without `call_tools` arg defaults to `call_tools='all'`. The test agent has `_compute_metric` registered; TestModel auto-generates a `formula` arg ('a') which hits `UnknownMetricFormulaError`. Agent tests failed.

**Root cause:** The plan assumed TestModel with `custom_output_args` would skip tool calls and just return the canned output. In pydantic-ai 1.96.0, the default is to call all tools before returning the final output.

**Solution:** Pass `call_tools=['_query_orders']` (or `call_tools=[]`) to control which tools the mock invokes. For the test that checks citation propagation, use `call_tools=['_query_orders']` so real citations flow through the message history. For the hallucinated-ID test, use `call_tools=[]` so available_citations is empty and the enforcer correctly rejects row 99999.

**Guardrail:** When using TestModel in pydantic-ai 1.96.0+, always specify `call_tools` explicitly. Never rely on the default. The tools that are called must be able to handle auto-generated args (or use `call_tools=[]`).

### 2026-05-14 (Phase 5) — pydantic-ai internal _messages module not public-exportable

**Problem:** `from pydantic_ai._agent_graph import _messages as pai_messages` imported `ToolReturnPart` from a private module. mypy errored: "Module does not explicitly export attribute '_messages'".

**Root cause:** `_agent_graph` is a private module; `_messages` within it is also private. The public API is `pydantic_ai.messages`.

**Solution:** Import `from pydantic_ai.messages import ToolReturnPart`. This is the public surface and mypy accepts it.

**Guardrail:** Always import pydantic-ai types from the public `pydantic_ai.messages` module, not from private `_agent_graph` internals. The public API is stable; the private one is not.

### 2026-05-14 (Phase 5) — GroundedAnswer cannot use extra="forbid" with PydanticAI structured output

**Problem:** PydanticAI's structured output mechanism serialises the output type's schema as a JSON schema tool call. With `extra="forbid"`, the JSON schema generation sometimes injects additional properties that conflict with the strict mode.

**Root cause:** PydanticAI 1.96.0 uses tool-call-based structured output where the output is returned as a function call argument. The internal bookkeeping may not align with extra="forbid" in all versions.

**Solution:** `GroundedAnswer` intentionally omits `extra="forbid"`. All other public types keep it. This exception is documented in the class docstring.

**Guardrail:** When a Pydantic model is used as `output_type` in a PydanticAI Agent, test `extra="forbid"` empirically before enabling it. If it breaks the agent loop, document the exception and move on.

### 2026-05-14 (Phase 4 live smoke) — Shopify "Protected Customer Data" gate is separate from OAuth scopes

**Problem:** After completing OAuth and getting a token with `read_orders, read_customers, read_products, read_inventory` scopes, the first sync hit `GET /admin/api/2026-04/orders.json` → **403 Forbidden** with body: `"This app is not approved to access REST endpoints with protected customer data."` All four scopes were on the token; sync still failed.

**Root cause:** Shopify introduced "Protected Customer Data" gating in API 2024-04+ as a SEPARATE consent surface on top of OAuth scopes. Any endpoint that returns customer-bearing data (orders.json, customers.json) requires the app to declare which protected fields it needs (name, email, phone, address) under "Customer data access" in the Partner Dashboard. Without that declaration, `read_orders` alone is insufficient. For App Store review, declarations need approval; for dev stores, self-declaration is auto-granted.

**Solution:** In Partner Dashboard → AI-Munim → Versions → "Protected customer data access": check Store management + Analytics + App functionality as data-use reasons, then select Name + Email + Phone + Address under "Protected customer fields (optional)". Save + release new version + uninstall the app from the dev store + reinstall (Shopify binds protected-data permission at install time; existing tokens can't be upgraded in place).

**Guardrail:** Any future Shopify integration must declare protected customer data access at the same time as scope configuration. Document in README that reviewers need to walk this step. If we ever go multi-store, add a sanity check in `validate_credential` that hits `/orders.json?limit=1` (not just `/shop.json`) so a 403 here surfaces at install time rather than first sync.

### 2026-05-14 (Phase 4 live smoke) — `/api` prefix is a Vite dev-proxy convention, NOT a backend route prefix

**Problem:** Set `SHOPIFY_OAUTH_REDIRECT_URI=http://localhost:8000/api/connectors/shopify/oauth/callback` in the Phase 4 plan and `.env`. Shopify dutifully called that URL during the OAuth callback. Our backend serves connectors at plain `/connectors/...` — got a 404 envelope back instead of completing the OAuth handshake.

**Root cause:** The `/api/` prefix lives in two places in our setup: (1) frontend ky client prepends it to every request, (2) Vite dev proxy strips it before forwarding to localhost:8000. So `/api` is only a frontend ↔ proxy convention; the backend has never seen it. Easy to misread the prefix as a backend route prefix when both ends of the dev pipeline talk about `/api`.

**Solution:** Changed `SHOPIFY_OAUTH_REDIRECT_URI` to `http://localhost:8000/connectors/shopify/oauth/callback` (no /api) + matching update in the Partner App's "Allowed redirection URLs". Updated `.env.example`'s line with an explanatory comment.

**Guardrail:** Any URL that Shopify (or any external service) hits MUST be the real backend URL — never the Vite-proxied one. The mental model: `/api/*` exists only inside the frontend bundle and Vite's proxy; the moment a third party hits our backend, it's at bare paths. Add to README's deployment notes when we write it.

### 2026-05-14 (Phase 4 live smoke) — Shopify CLI `store auth` issues online tokens; orderCreate requires offline

**Problem:** Trying to seed test orders via `shopify store execute --query 'mutation { orderCreate(...) }'` returned: `"Access denied for orderCreate field. Required access: write_orders access scope. Also: This mutation is only accessible to apps authenticated using offline tokens."` We had write_orders on the CLI auth.

**Root cause:** Shopify has two token types — online (per-user session, expires when user logs out) and offline (long-lived, app-level). `shopify store auth` issues ONLINE tokens. `orderCreate` (the import-orders mutation) is gated to offline tokens because it's meant for app-side data import, not interactive user actions. Our own app's OAuth flow produces offline tokens — but we only requested read scopes, so it can't write either.

**Solution:** Switched to `draftOrderCreate` + `draftOrderComplete(paymentPending: true|false)` — draft order mutations accept online tokens. `paymentPending: true` produces a PENDING order (COD-equivalent), `false` produces PAID. Three test orders created via two CLI calls each.

**Guardrail:** When seeding test data via the CLI, prefer `draftOrderCreate` over `orderCreate`. If we ever need to programmatically create orders from our backend (e.g., for an auto-reordering agent), add `write_orders` to our app's scopes and the offline token is already what we have.

### 2026-05-14 (Phase 4 live smoke) — Shopify rejects `.in` email domain on order create

**Problem:** First `draftOrderCreate` failed with `userErrors: [{"field": ["email"], "message": "Email contains an invalid domain name"}]` for `aarav@example.in`.

**Root cause:** Shopify maintains an "invalid email domain" list — `example.in` is on it (likely because the .in TLD is reserved for India and `example.*` domains are reserved for documentation). `example.com` is on the allowlist.

**Guardrail:** Test fixtures and seed scripts use `@example.com`. If we need geographically realistic emails in test data, use real-looking domains (`@gmail.com`, `@outlook.in` would work).

### 2026-05-14 (Phase 4) — mypy reports "Missing named argument" for Pydantic Settings required fields

**Problem:** After adding required fields (no defaults) to `Settings`, `uv run mypy src` failed with `Missing named argument "shopify_client_id" for "Settings"` (and 4 others) at the `get_settings()` call site `Settings()`. Mypy treats the call as a regular Python constructor call, not knowing that Pydantic Settings reads from env.

**Root cause:** Mypy doesn't natively understand pydantic-settings' env-reading mechanism. Without the pydantic mypy plugin, required fields look like missing positional args.

**Solution:** Added `[tool.mypy]` section to `pyproject.toml` with `plugins = ["pydantic.mypy"]` and `strict = true`. The pydantic plugin teaches mypy about field population from env, so `Settings()` with no explicit args is understood as valid.

**Guardrail:** Any project using pydantic-settings with required fields (no defaults) must have the pydantic mypy plugin configured, or mypy will emit spurious errors on every `Settings()` constructor call.

### 2026-05-14 (Phase 4) — Task 4 connector test needed updating when validate() behavior changed

**Problem:** The existing `test_shopify_validate_accepts_demo_and_defers_real_credentials` test expected `NotImplementedError` for connected credentials. Phase 4 Task 7 changed `validate()` to actually call `client.validate_credential()` for connected credentials, making the test incorrect.

**Root cause:** Task 4 (remove ABC methods) and Task 7 (real validate) were planned as sequential but the test from Phase 2 asserted the Phase 2 behavior (NotImplementedError for connected creds). When Task 7 updated the behavior, the test needed updating.

**Solution:** Updated the test in Task 7: split into `test_shopify_validate_accepts_demo_credential` (always passes) and `test_shopify_validate_raises_for_unknown_status` (unknown status raises). The connected-credential path is now covered by `test_client_real.py::test_validate_returns_true_when_shop_endpoint_returns_200` and `test_validate_returns_false_on_401`.

**Guardrail:** When a phase changes a concrete method's behavior (not just its interface), check if existing tests for that method need updating. Stub-behavior tests (testing that NotImplementedError is raised) are correct in the stub phase but wrong once the real implementation lands.

### 2026-05-14 (Phase 3 review) — a typed error class that's never raised IS a contract bug

**Problem:** Phase 3 declared `ConnectorSyncError` with `code = "connector.sync_failed"` but never raised it. The sync endpoint instead let untyped exceptions (RuntimeError, KeyError) bubble to the global handler, which classified them as `system.unexpected`. Frontend branches on `code`, so a sync failure looked indistinguishable from any other internal error.

**Root cause:** YAGNI was misapplied. The class was added defensively without a callsite. Per the convention "every error code in the enum is either used or scheduled," an unused error code that *should* be used is worse than not having it — it implies a contract that doesn't exist.

**Solution:** Wrapped the `connector.sync_full(ctx)` call in `sync_connector` to catch non-`MunimError` exceptions and re-raise as `ConnectorSyncError` with `from exc` chaining (preserves the original traceback for observability). MunimError subclasses propagate unchanged so typed sub-errors like `connector.rate_limited` will surface correctly when Phase 4 introduces them. Added `test_sync_wraps_untyped_exception_as_connector_sync_failed` with a stub connector that always raises — the test fails without the wrap, passes with it.

**Guardrail:** Every typed error class in `shared/errors.py` or a module's `service.py` must have at least one `raise` site **and** at least one test that exercises the path. If it doesn't, delete the class. Dead error codes mislead the frontend's `code`-based branching as much as missing ones do.

### 2026-05-13 — `ruff` N818 requires exception class names to end in `Error`

**Problem:** `uv run ruff check src` failed with `N818 Exception name 'ValidationFailed' should be named with an Error suffix`.

**Root cause:** `ruff`'s pep8-naming rule N818 enforces the convention that exception classes end in `Error`. `MunimError` was fine; `ValidationFailed` (subclass) was not.

**Solution:** Renamed `ValidationFailed` → `ValidationFailedError` in `apps/api/src/munim/shared/errors.py`. Kept N818 enabled in `pyproject.toml` so future violations are caught.

**Guardrail:** Every domain-error subclass in `shared/errors.py` ends in `Error`. New pattern: `ConnectorRateLimitedError`, `LLMUnavailableError`, etc. Not `ConnectorRateLimited`, etc.

### 2026-05-13 (Phase 2 review) — `datetime` equality is point-in-time, not tzinfo-identity

**Problem:** `test_maps_placed_at_to_utc` asserted `order.placed_at == datetime(2026, 5, 10, 3, 45, 32, tzinfo=UTC)` to prove the mapper normalized to UTC. The test passed for weeks of work even though the mapper was actually storing `+05:30`-aware datetimes — `_parse_iso` had a no-op `dt.astimezone(tz=dt.tzinfo)` instead of `dt.astimezone(UTC)`. The reviewer subagent caught both the bug and the dishonest test.

**Root cause:** Python's `datetime.__eq__` compares the absolute moment in time, ignoring `tzinfo` identity. So `datetime(2026, 5, 10, 9, 15, 32, +05:30) == datetime(2026, 5, 10, 3, 45, 32, UTC)` is `True`. The test was vacuous coverage.

**Solution:** Two fixes. (a) `_parse_iso` now `dt.astimezone(UTC)` so the result is always UTC. (b) `test_maps_placed_at_to_utc` now asserts `order.placed_at.tzinfo is UTC` first — the identity check that would have caught the bug. The equality assertion stays as belt-and-braces.

**Guardrail:** When testing timezone normalization, assert the `tzinfo` field directly (identity, `is UTC`). Equality alone is insufficient because Python compares instants. This applies broadly: any test claiming "stored as UTC" must include an identity check, not just equality.

### 2026-05-13 (Phase 2 review) — silent naive-datetime fallback in `_parse_iso`

**Problem:** `_parse_iso` had `return dt.astimezone(tz=dt.tzinfo) if dt.tzinfo else dt` — when the input had no timezone, it silently returned a naive datetime. Naive datetimes in SQLite TIMESTAMP columns lose their intended timezone irrecoverably.

**Root cause:** The plan accepted a "tolerant" parse path. Per §10 of `docs/conventions.md` that's a silent fallback.

**Solution:** `_parse_iso` now raises `ValueError` when `dt.tzinfo is None`. Added `test_mapper_raises_when_created_at_lacks_timezone` to lock the contract.

**Guardrail:** Any datetime parsing helper must raise on missing tzinfo, not silently produce a naive result. This generalizes: any "parse / convert" helper that has a fallback branch needs an explicit `raise` for the unknown-input case unless we've decided otherwise (and recorded why).

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

### 2026-05-14 — Phase 5: enforcer `_PROXIMITY_CHARS = 64` window

**Decision:** The citation enforcer covers any numeric claim whose span falls within 64 characters BEFORE the start of a `[cite:...]` marker. 64 was chosen to cover the longest realistic "N thing[s] worth ₹X,XXX[cite:...]" where both the count and the currency appear before a single trailing cite. Tuned empirically against the 13 enforcer tests.

**Why:** A smaller window (e.g., 10) would incorrectly strip "12 orders worth ₹15,750[cite:1]" because "12 orders" is more than 10 chars from the cite. A larger window (e.g., 200) would incorrectly keep uncited numbers in adjacent sentences. 64 is the sweet spot for single-clause citations.

**Revisit if:** The LLM starts writing multi-line citations where the number and the cite are separated by a semicolon or newline. In that case, consider a proximity model based on sentence boundaries rather than character count.

### 2026-05-14 — Phase 5: TestModel.call_tools for citation plumbing in agent tests

**Decision:** Agent integration tests use `TestModel(call_tools=['_query_orders'], custom_output_args=canned)` rather than `call_tools=[]`. This forces the query tool to run against the real seeded DB, populating `available_citations` with real row IDs. The canned answer then cites those real IDs, and the enforcer accepts it. Tests that check hallucination-rejection use `call_tools=[]` so `available_citations` is empty and any cited ID is by definition hallucinated.

**Why:** The alternative (mocking `available_citations` directly) would test the enforcer in isolation — which is already tested in `test_enforcer.py`. The agent test is specifically testing the end-to-end citation plumbing: tool runs → citations collected → enforcer called with real citations. Bypassing the tool would make the test vacuous per §13.4.

### 2026-05-14 — Phase 4: `authorize_url`/`exchange_code` removed from BaseConnector ABC

**Decision:** Dropped `authorize_url` and `exchange_code` from `BaseConnector` ABC. Each provider's OAuth is now in its own `oauth_<name>.py` (e.g., `oauth_shopify.py`). Phase 5 will add `oauth_meta_ads.py`, etc.

**Why:** OAuth contract differs per provider: Shopify uses URL params + HMAC verification; Meta uses form post + PKCE; Shiprocket uses username/password. Forcing one ABC method signature for all would either use the wrong parameter set or require every connector to accept `**kwargs` (which defeats static typing). This is the Liskov Substitution Principle: an ABC should only abstract what all subclasses share identically. Auth is not that.

**Revisit if:** A future connector happens to have an identical auth shape to Shopify, suggesting an `OAuthConnector` mixin might be worth extracting. Threshold: same shape for 3+ connectors.

### 2026-05-14 — Demo fixture lives at apps/api/data/fixtures/, not in tests/

**Decision:** Moved the Shopify orders fixture from `tests/fixtures/` to
`apps/api/data/fixtures/shopify/orders.json`. Tests now point at the same
file via a small `_paths.py` helper.

**Why:** The running app's connect endpoint needs a stable path that isn't
inside a tests directory. One file used by both demo and tests beats two
copies that can drift apart.

**Revisit if:** the fixture grows to MB scale and slows test discovery, or
if we want test-specific edge cases that shouldn't pollute the demo.

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
- 2026-05-14 — Phase 5 implementation (chat layer + citation contract): executed by Claude Sonnet 4.6 as a coder subagent. Key adjustments vs. plan: (1) `ToolReturnPart` imported from public `pydantic_ai.messages` not private `_agent_graph._messages`; (2) `TestModel(call_tools=[...])` added to control tool invocation in agent tests — plan assumed `custom_output_args` would skip tools, but pydantic-ai 1.96.0 defaults to calling all tools; (3) `GroundedAnswer` kept without `extra="forbid"` to avoid structured-output schema conflicts; (4) regex pattern restructured into `_ENTITY_NOUNS` constant to avoid line-length violation in VERBOSE regex comments; (5) `₹` in test strings replaced with `Rs.` for Windows terminal encoding compatibility in test assertions (enforcer regex handles both).
