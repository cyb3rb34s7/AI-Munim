# Phase 9 — Multi-tenant backbone, demo link, scalability proof, deployment

> **For agentic workers:** ONE implementer dispatch for the whole phase (8 tasks). Commit per task; the plan's commit messages are templates, not exact strings. Report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Use `superpowers:subagent-driven-development`.
>
> **Comment discipline (paid lesson across Phases 5–8):** default to NO comments. WHY-only when non-obvious. NEVER task/phase/reviewer-referential comments. NEVER narrate what well-named code does.
>
> **API contracts (Phase 7 paid lesson):** before writing any frontend client touching `/auth/*`, Read the actual backend `auth/router.py` + Pydantic schemas in the same step. Do not infer shapes from this plan.

**Goal:** Close the brief's remaining gap — the "10k merchants" scalability story — by making multi-tenancy a real property of the running system rather than a future-tense paragraph. Every visitor to the deployed demo gets their own merchant + isolated dataset via an anonymous session cookie. The frontend gets a landing page and a one-click "Start demo" flow. Architecture docs and README upgrade their scalability sections to reflect the proven (not just sketched) multi-tenant reality. Deploy to Render so a reviewer can click a link and try the product.

**Non-goal (deferred):** real authentication (email/password, magic-link, OAuth providers). The cookie session is the v0 mechanism; real auth is a Phase 10 if time permits. Reviewers won't sign up — they'll click a link, optionally type a display name, and start using the product immediately.

---

## Architecture overview (the four moving parts)

### 1. Anonymous session cookie

A signed cookie carries the visitor's `merchant_id`. Mechanism: starlette's `SessionMiddleware` (battle-tested, ships with FastAPI's underlying stack, uses `itsdangerous` for HMAC signing). The middleware reads + writes a single cookie; cookie value is `{"merchant_id": "m_abc123", "user_id": "u_xyz789"}` serialized and signed. Secret key from env (`SESSION_SECRET`).

- **First request without cookie** → backend dependency creates a fresh `Merchant` + `User` row → puts ids in `request.session` → middleware automatically serializes + signs + sets cookie on response.
- **Every subsequent request** → middleware reads + verifies signature → puts session dict on `request.session` → dependency derives `merchant_id`.
- **Cookie forgery prevented** by HMAC; cookie expiry 30 days.

### 2. Multi-tenant code refactor

Every endpoint currently uses `DEFAULT_MERCHANT_ID = "m_default"` from `shared/db.py`. Phase 9 introduces `get_current_merchant_id` as a FastAPI dependency that reads the session. The refactor is **mechanical**: ~25 files where `DEFAULT_MERCHANT_ID` appears at a route level. Service-level functions already take `merchant_id` as a parameter — they don't change.

Tests keep `DEFAULT_MERCHANT_ID` as a fixture-injected value (a per-test scratch merchant). The test conftest creates the merchant up-front and the FastAPI test client carries an authenticated cookie for it.

### 3. Per-merchant demo seeding

On `POST /auth/start`:
1. Create `Merchant` + `User` rows.
2. Synchronously enable + sync Meta Ads demo (40 ad_spend rows from existing fixture).
3. Synchronously enable + sync Shiprocket demo (50 shipment rows from existing fixture).
4. Insert 6 mock Shopify order rows directly into `record` (real-shape Shopify Order payloads, customer hashes matching Shiprocket Customer A + B so the agent narrative lands immediately on first chat/agent run).
5. Set session cookie + return 200.

The seeding is bounded (~96 rows, sub-second) and idempotent (re-running creates no duplicates because of `(merchant_id, source_system, source_id)` natural key).

### 4. Deployment to Render

- **Single service** model: backend serves both the FastAPI API at `/api/*` AND the built frontend SPA at `/`. One process, one port, one URL.
- Backend mounts `apps/web/dist` as a static directory. Vite's `build` produces `dist/index.html` + bundled assets.
- Persistent disk for SQLite at `/data/munim.sqlite`.
- Env vars: `SESSION_SECRET`, `CREDENTIALS_ENCRYPTION_KEY`, `OPENAI_API_KEY`, `FRONTEND_BASE_URL` (self-referential URL for OAuth callbacks if used).
- Shopify real OAuth is **disabled on the deployed environment** via an env feature flag (`SHOPIFY_OAUTH_ENABLED=false`). The connector card shows the same demo-mode UX as Meta + Shiprocket. Real OAuth stays in the code for local dev.

---

## File map

**New (backend):**
- `apps/api/src/munim/modules/auth/__init__.py`
- `apps/api/src/munim/modules/auth/router.py` (`POST /auth/start`, `GET /auth/me`, `POST /auth/logout`)
- `apps/api/src/munim/modules/auth/service.py` (creates Merchant + User, calls seed)
- `apps/api/src/munim/modules/auth/seed.py` (per-merchant demo seeding)
- `apps/api/src/munim/modules/auth/schemas.py`
- `apps/api/src/munim/modules/auth/dependencies.py` (`get_current_merchant_id`, `get_current_user`)
- `apps/api/src/munim/modules/auth/tests/test_router.py`
- `apps/api/src/munim/modules/auth/tests/test_seed.py`
- `apps/api/src/munim/connectors/shopify/fixtures/orders.json` (6 mock orders, customer hashes matching Shiprocket fixture)
- `apps/api/src/munim/models/user.py` (new `User` SQLModel)
- `apps/web/src/modules/auth/api/client.ts`
- `apps/web/src/modules/auth/hooks/useAuth.ts`
- `apps/web/src/modules/auth/AuthProvider.tsx` (context + ProtectedRoute)
- `apps/web/src/modules/auth/components/StartDemoForm.tsx`
- `apps/web/src/pages/LandingPage.tsx`
- `apps/web/src/pages/StartPage.tsx`
- `Dockerfile` (single-image backend that serves frontend dist)
- `render.yaml` (Render service definition)

**Modified (backend) — DEFAULT_MERCHANT_ID → session dependency:**
- `apps/api/src/munim/modules/connectors/router.py`
- `apps/api/src/munim/modules/records/router.py`
- `apps/api/src/munim/modules/chat/router.py`
- `apps/api/src/munim/modules/agent_runs/router.py`
- `apps/api/src/munim/modules/connectors/demo_connect.py`
- `apps/api/src/munim/main.py` (mount SessionMiddleware + auth router + static files for production)
- `apps/api/src/munim/shared/db.py` (keep `DEFAULT_MERCHANT_ID` as a test-only constant; init_db no longer auto-creates it)
- `apps/api/src/munim/shared/config.py` (add `session_secret`, `shopify_oauth_enabled`, `frontend_dist_path`)
- `apps/api/conftest.py` (new fixture: `auth_client` returns a TestClient with a fresh merchant + signed cookie)
- 6 tests in `tests/test_router.py` etc. that hardcode `/connectors/<name>/connect`-style paths — switch to using the new `auth_client` fixture
- `apps/api/pyproject.toml` (add `itsdangerous` if not already pulled in transitively; it ships with starlette so likely not needed)

**Modified (frontend):**
- `apps/web/src/main.tsx` (wrap routes in `AuthProvider`)
- `apps/web/src/router.tsx` (`/` → LandingPage, `/start` → StartPage, everything else behind `<ProtectedRoute>`)
- `apps/web/src/shared/api/client.ts` (add `credentials: 'include'` to ky config so cookies fly)
- `apps/web/src/modules/connectors/components/ConnectorCard.tsx` (hide "Connect to your store" button when `import.meta.env.VITE_SHOPIFY_OAUTH_ENABLED !== 'true'`)
- `apps/web/vite.config.ts` (proxy already at 127.0.0.1:8000 from Phase 7 fix)

**Modified (docs):**
- `docs/architecture.md` §10 (rewrite "Scale story" to reflect demonstrated multi-tenancy)
- `README.md` (rewrite — first impression for a reviewer)
- `CHANGELOG.md`
- `context.md`

**Phase 8 cleanup nits (modified):**
- `apps/web/src/modules/connectors/hooks/useConnectMutation.ts` (delete — dead code)
- `apps/web/src/modules/connectors/api/postConnect.ts` (delete — dead code)
- `apps/web/src/modules/connectors/components/ConnectorsGrid.tsx` (replace silent `return null` with explicit EmptyState)

---

## Task 1 — Auth backbone: session middleware + dependency + User model

**Files:** `models/user.py`, `modules/auth/{dependencies,schemas}.py`, `main.py` (mount middleware), `shared/config.py`.

- [ ] Add `User` SQLModel — minimal: `id` (str ULID), `merchant_id` (FK), `display_name` (str, default "Demo User"), `created_at` (UTC). New table `user`. No password column; this is anonymous session, not real auth.
- [ ] Add to `shared/config.py`:
  - `session_secret: SecretStr` — required, no default. Tests pass via `monkeypatch.setenv`.
  - `session_cookie_max_age_days: int = 30`
  - `shopify_oauth_enabled: bool = True` — local dev keeps Shopify OAuth; deployed env sets False.
  - `frontend_dist_path: str | None = None` — when set, FastAPI mounts the dist as static files at `/`.
- [ ] `modules/auth/dependencies.py`:
  ```python
  async def get_current_merchant_id(request: Request) -> str:
      merchant_id = request.session.get("merchant_id")
      if not merchant_id:
          raise UnauthenticatedError(message="No active session.")
      return merchant_id

  async def get_current_user(...) -> User:
      ...
  ```
- [ ] New `UnauthenticatedError(MunimError)` with code `auth.unauthenticated`, HTTP 401. Register `AUTH_UNAUTHENTICATED` in `ErrorCode` enum.
- [ ] `modules/auth/schemas.py`:
  ```python
  class StartDemoRequest(BaseModel):
      display_name: str | None = Field(default=None, max_length=80)

  class CurrentUser(BaseModel):
      merchant_id: str
      user_id: str
      display_name: str
      created_at: datetime
  ```
- [ ] In `main.py`, mount `SessionMiddleware` with `secret_key=settings.session_secret.get_secret_value()`, `max_age=settings.session_cookie_max_age_days * 86400`, `same_site="lax"`, `https_only=False` (overridden to True via env in prod via `SESSION_HTTPS_ONLY=true` if added).
- [ ] Tests: dependency raises `UnauthenticatedError` when session is empty; happy path returns the merchant_id; signature tampering is rejected (starlette handles this for us — write one test that asserts a manually-edited cookie value returns 401).
- [ ] Lint + format + mypy + full suite. Commit.

Commit message: `feat(auth): SessionMiddleware + User model + get_current_merchant_id dependency`

---

## Task 2 — Auth router: POST /auth/start, GET /auth/me, POST /auth/logout

**Files:** `modules/auth/{router,service}.py`, register router in `main.py`, tests.

- [ ] `service.py`:
  - `start_demo_session(session, display_name) -> CurrentUser`: creates Merchant + User, returns CurrentUser. The session-cookie write happens at the router via `request.session[...] = ...`.
  - `get_current_user_info(session, merchant_id, user_id) -> CurrentUser`: looks up + returns.
- [ ] `router.py`:
  - `POST /auth/start`: accepts `StartDemoRequest`, creates Merchant + User, **triggers seeding** (Task 3), writes `merchant_id` + `user_id` into `request.session`, returns `CurrentUser`.
  - `GET /auth/me`: returns the current user — 401 if no session.
  - `POST /auth/logout`: clears `request.session`, returns 204.
- [ ] Tests in `test_router.py`:
  - Happy path: POST /auth/start → 200, session cookie set, GET /auth/me returns the same merchant.
  - Display name optional: missing display name → user created with default "Demo User".
  - Display name max length: 81-char name → 422 validation error.
  - GET /auth/me without cookie → 401 `auth.unauthenticated`.
  - POST /auth/logout clears the session; subsequent GET /auth/me → 401.
  - Tampered cookie → 401 (the starlette middleware should reject it before our handler runs).
  - Multi-merchant isolation: two distinct start-demo calls produce two distinct merchant_ids; data created by one is not visible to the other.
- [ ] Lint + suite. Commit.

Commit message: `feat(auth): POST /auth/start + GET /auth/me + POST /auth/logout endpoints`

---

## Task 3 — Per-merchant demo seeding

**Files:** `modules/auth/seed.py`, `connectors/shopify/fixtures/orders.json` (NEW), `modules/auth/tests/test_seed.py`.

- [ ] Build `connectors/shopify/fixtures/orders.json`: 6 mock Shopify Admin API order responses (real-shape, customer email + phone fields populated). Customers:
  - 2 orders for `rohan@example.com` (Customer A — matches Shiprocket high-RTO fixture customer).
  - 2 orders for `priya@example.com` (Customer B — clean record).
  - 1 order for `amit@example.com` (Customer C).
  - 1 one-off for a guest customer with phone only.
  Distribution: 4 prepaid + 2 COD (so the agent has COD orders to score on first run). Pincodes: 110001 (high-risk), 560001 (low-risk), 700001 (high-risk).
- [ ] `seed.py`:
  ```python
  async def seed_new_merchant(session: Session, merchant_id: str) -> None:
      _seed_shopify(session, merchant_id)     # insert 6 record rows directly
      await _seed_meta(session, merchant_id)  # call MetaAdsConnector.sync_full
      await _seed_shiprocket(session, merchant_id)  # call ShiprocketConnector.sync_full
  ```
  - Shopify: load fixture, map each row via `map_shopify_order_to_normalized`, write to `record` via `RowSink`. Then upsert a `connector_credentials` row for Shopify with `status=demo` so the Connectors page shows Shopify as "connected (demo)".
  - Meta: enable demo via `connect_demo_endpoint` shape (or call the service helper directly), then run `MetaAdsConnector.sync_full`.
  - Shiprocket: same shape.
- [ ] Wire `seed_new_merchant` into `POST /auth/start`'s flow.
- [ ] Tests:
  - After seeding a new merchant, `record` has 96 rows (6 orders + 40 ad_spend + 50 shipments) — all scoped to the new merchant_id, zero leak into other merchants.
  - Idempotency: calling `seed_new_merchant` twice on the same merchant_id writes no duplicate rows (the natural key handles it).
  - Customer hash join: the Shopify seed's `customer_source_id` for `rohan@example.com` matches the Shiprocket fixture's customer A hash (so the agent's `customer_rto_rate` will return real history).
  - Isolation: merchant A's seed produces no rows visible to merchant B's session.
- [ ] Lint + suite. Commit.

Commit message: `feat(auth): seed new merchant with 96 rows across Shopify + Meta + Shiprocket demos`

---

## Task 4 — Refactor DEFAULT_MERCHANT_ID → session dependency across all routers

**Files:** all 6 router files + their tests, `conftest.py`, `shared/db.py`.

This is the **mechanical sweep** — the load-bearing multi-tenant refactor.

- [ ] In every router file, replace `from munim.shared.db import DEFAULT_MERCHANT_ID, get_session` with `from munim.shared.db import get_session` + `from munim.modules.auth.dependencies import get_current_merchant_id`.
- [ ] In every endpoint, replace `DEFAULT_MERCHANT_ID` with a `merchant_id: str = Depends(get_current_merchant_id)` parameter. The endpoint body uses `merchant_id` directly.
- [ ] In `shared/db.py`: keep `DEFAULT_MERCHANT_ID = "m_default"` as a test-only constant; remove the `init_db` auto-creation of this merchant (it now lives in fixtures only).
- [ ] In `apps/api/conftest.py`: new fixture `auth_client` that, on creation, posts to `/auth/start` (with the running TestClient) to mint a fresh merchant + capture the session cookie. Existing `client` fixture stays for tests that intentionally hit unauthenticated paths (landing, /auth/start itself).
- [ ] Update existing test files where they post to `/connectors/<name>/...`, `/chat/messages`, `/agents/.../run`, `/agent-runs`, `/records` etc. to use `auth_client` instead of `client`. The test_router.py changes are mechanical.
- [ ] One additional test category: **isolation** — for each protected endpoint, write one test that asserts data created in merchant A's session is not visible in merchant B's session. (Spot-check on 3 representative endpoints: records, agent-runs, connectors.)
- [ ] One additional test: **unauthenticated request** — every protected endpoint returns 401 when called via the unauthenticated `client` fixture.
- [ ] Lint + suite. Commit.

Commit message: `refactor(api): every endpoint derives merchant_id from the session, not the hardcoded default`

---

## Task 5 — Frontend: AuthProvider + landing + start pages + protected routing

**Files:** `apps/web/src/modules/auth/**`, `apps/web/src/pages/{LandingPage,StartPage}.tsx`, `apps/web/src/router.tsx`, `apps/web/src/shared/api/client.ts`.

- [ ] `modules/auth/api/client.ts`:
  - Zod schemas matching backend `CurrentUser`, `StartDemoRequest`.
  - `startDemo({display_name})` → POST /auth/start.
  - `fetchCurrentUser()` → GET /auth/me. Returns `null` (not throws) on 401 — the un-authenticated state is normal during landing.
  - `logout()` → POST /auth/logout.
- [ ] `shared/api/client.ts`: add `credentials: 'include'` to ky's options so the session cookie is sent on every request.
- [ ] `modules/auth/hooks/useAuth.ts`:
  - TanStack Query for `fetchCurrentUser` keyed `['auth', 'me']`.
  - `useStartDemo` mutation invalidates `['auth', 'me']` on success.
- [ ] `modules/auth/AuthProvider.tsx`:
  - `<AuthProvider>` wraps the app, fetches /auth/me once, exposes `user | null | loading`.
  - `<ProtectedRoute>` reads the context, renders children if user exists, otherwise navigates to `/`.
- [ ] `pages/LandingPage.tsx`: marketing page.
  - Hero: "Munim — your AI employee for D2C." Sub-headline gestures at the brief: chat with citations, deterministic agent, three connectors.
  - Three feature blocks (cards): Universal Data Model, Grounded Chat, RTO Risk Mitigator. Each block one short sentence + an icon (lucide).
  - Single CTA button "Try the live demo" → routes to `/start`.
  - Footer with a link to GitHub repo.
- [ ] `pages/StartPage.tsx`: minimalist screen.
  - Centered card. Optional `<input>` for display name (placeholder "Demo User"). "Start demo" button → fires `useStartDemo` → on success, navigates to `/chat`.
  - Below the form, a small explainer: "We'll set up a private demo workspace pre-populated with realistic Shopify, Meta Ads and Shiprocket data. No sign-up, no email."
- [ ] `router.tsx`:
  - `/` → LandingPage (unauthenticated).
  - `/start` → StartPage (unauthenticated; if user already has session, redirect to `/chat`).
  - All other routes (`/chat`, `/agents`, `/connectors`, `/records`) wrapped in `<ProtectedRoute>` → redirect to `/` if no session.
- [ ] Phase 8 cleanup: delete `useConnectMutation.ts` + `postConnect.ts`; fix `ConnectorsGrid.tsx`'s silent `return null` → render an explicit EmptyState.
- [ ] Lint + typecheck + build. Commit.

Commit message: `feat(web): AuthProvider + landing page + start-demo flow + protected routes`

---

## Task 6 — Deployment: Dockerfile + Render config + serve frontend from backend

**Files:** `Dockerfile`, `render.yaml`, `.dockerignore`, README deploy section.

- [ ] Multi-stage `Dockerfile` at repo root:
  - Stage 1: Node 22 alpine — copy `apps/web/`, install with pnpm, build (`pnpm build` → `apps/web/dist`).
  - Stage 2: Python 3.11 slim — install `uv`, copy `apps/api/`, install deps, copy `apps/web/dist/` from stage 1 into `/app/static/`, set `FRONTEND_DIST_PATH=/app/static`, expose 8000, run `uvicorn munim.main:app --host 0.0.0.0 --port $PORT`.
- [ ] In `apps/api/src/munim/main.py`, after `create_app()`:
  ```python
  if settings.frontend_dist_path:
      from fastapi.staticfiles import StaticFiles
      app.mount("/", StaticFiles(directory=settings.frontend_dist_path, html=True), name="frontend")
  ```
  Mount order matters: API routes must be declared before the static mount (FastAPI evaluates routes in declaration order; `/` last-resort catch-all goes after `/api/*`, `/auth/*`, `/chat/*`, `/agents/*`, `/agent-runs/*`, `/connectors/*`, `/records/*`, `/health`).
- [ ] **API path prefix:** to keep the dev proxy convention (`/api/*` → backend) without rewriting every router, add a prefix in production via `app.mount("/api", api_app)` pattern OR keep current routes and have Vite's prod proxy write `/api/*` → unprefixed — pick whichever is cleaner. **Recommendation:** make all router prefixes start with `/api/` in code; Vite's dev proxy currently strips `/api/`, so for dev it still hits unprefixed routes — adjust the proxy to NOT strip. Result: routes match in dev and prod without conditional logic.
- [ ] `.dockerignore`: exclude `node_modules`, `.venv`, `__pycache__`, `apps/api/.env`, `dist`, `*.sqlite`, `.git`.
- [ ] `render.yaml`:
  ```yaml
  services:
    - type: web
      name: munim
      runtime: docker
      dockerfilePath: ./Dockerfile
      plan: free
      disk:
        name: data
        mountPath: /data
        sizeGB: 1
      envVars:
        - key: DATABASE_URL
          value: sqlite:////data/munim.sqlite
        - key: SESSION_SECRET
          generateValue: true
        - key: CREDENTIALS_ENCRYPTION_KEY
          generateValue: true
        - key: OPENAI_API_KEY
          sync: false  # set manually in Render dashboard
        - key: SHOPIFY_OAUTH_ENABLED
          value: "false"
        - key: APP_ENV
          value: production
  ```
- [ ] Smoke-build the Docker image locally (`docker build -t munim . && docker run -p 8000:8000 -e SESSION_SECRET=xxx ... munim`); verify landing page renders + /auth/start works + /chat works in the container.
- [ ] Commit.

Commit message: `feat(deploy): Dockerfile + render.yaml + serve frontend dist from FastAPI in prod`

---

## Task 7 — Scalability narrative upgrade

**Files:** `docs/architecture.md` §10, `README.md` (rewrite).

- [ ] Rewrite `docs/architecture.md` §10:
  - Update §10.1 "What breaks first" — multi-tenant is no longer rank 6 ("v0 has no auth"). It moves to "shipped in v0 as anonymous-session cookies; row-level security for paid customers is the next step." Sync orchestration moves up; LLM cost stays where it is.
  - Update §10.2 "What we built in v0 to absorb the future" — replace `merchant_id` on every row "even though there's one merchant" with `merchant_id` on every row PROVEN under N visitors during demo. Add: "anonymous session cookie + per-visitor merchant + per-merchant pre-seeding". Add: "the Postgres migration is one SQLALCHEMY_DATABASE_URL change; row-level security is one DDL change."
  - Update §10.3 "What we sketched but did not build" — the load test harness is still sketched; add a concrete `scripts/loadtest_visitors.py` description (N parallel visitors hitting /auth/start + /chat).
- [ ] Rewrite `README.md`:
  - Title + tagline.
  - "What it is" — 3 paragraphs mapping to the brief's 5 requirements.
  - "Try the live demo" — link to deployed URL.
  - "Run locally" — `docker-compose up` or split backend/frontend dev recipe.
  - Architecture diagram (link to `docs/architecture.md`).
  - "How the citation contract works" — 4-bullet summary.
  - "How the agent works" — 4-bullet summary.
  - "Scalability" — digest of §10; the headline "what breaks first" table.
  - "Honest limitations" — Shopify OAuth disabled on deployed (single-tenant gotcha); LLM cost ceiling; SQLite single-writer; Meta/Shiprocket as demo-mode.
  - "Tech choices" — short defenses for: PydanticAI, SQLModel, Tailwind v4, framer-motion, Render.
- [ ] Commit.

Commit message: `docs: rewrite README + upgrade architecture.md §10 for demonstrated multi-tenancy`

---

## Task 8 — Live deployed smoke + final commit + push

- [ ] Push to a branch, connect to Render via the dashboard, deploy. Wait for first build (~5-8 min for the multi-stage Dockerfile).
- [ ] Walk the smoke recipe on the deployed URL:
  1. Hit the URL; landing page renders.
  2. Click "Try the live demo" → /start.
  3. Type "Reviewer" as display name, click Begin → redirected to /chat. (Verify cookie was set in DevTools.)
  4. Chat: "How many orders do I have?" → response has 6 orders cited, sources are Shopify.
  5. /connectors → all three cards show "Connected (demo)" (Shopify is hidden-OAuth, demo-only on deployed).
  6. /agents → "Run agent now" → toast → row appears → click row → detail sheet shows decisions; Customer A's COD order proposes `convert_to_prepaid` with real Shiprocket-history-driven score.
  7. /records → 96 rows visible, mixed Shopify/Meta/Shiprocket.
  8. Open an incognito window, hit the URL: fresh merchant, no overlap with the first session.
  9. POST /auth/logout → reload → back at landing.
- [ ] Update `context.md`: bump Now → "Phase 9 deployed; reviewers can click <URL> to try the live demo."; Done; Next (Phase 10 — real auth if time).
- [ ] Update `CHANGELOG.md` with the Phase 9 entry.
- [ ] Final commit + push.

Commit message: `docs(phase-9): record live deployment + multi-tenant demo + scalability narrative upgrade`

---

## Self-review

**Brief coverage:**
- ≥3 connectors behind one abstraction — already done in Phase 8. Phase 9 adds per-merchant seeding so each visitor sees them populated.
- Universal data model with provenance — unchanged.
- Chat with citation contract — unchanged.
- ≥1 autonomous agent — unchanged.
- **Scalability story** — *moves from "sketched" to "demonstrated"*. Every visitor is a real merchant; isolation is tested; the Postgres migration is one config change.

**Type / name consistency:**
- Backend `CurrentUser` Pydantic schema mirrors frontend `currentUserSchema` Zod schema — verify side-by-side at write time (Phase 7 paid lesson).
- `merchant_id` field name consistent across DB column, Pydantic model, Zod schema, frontend types.
- Cookie name: `munim_session` (one constant in code, no magic strings).

**Test discipline (§13.4):**
- Auth tests pin: cookie tampering rejection, max-age behavior, session isolation across two test clients, seeding idempotency, customer-hash cross-connector join in seed data.
- Existing 213 tests stay green after the `auth_client` fixture migration. Estimate +30 new tests for auth/seeding/isolation.

**Past lessons baked in:**
- Comment discipline: no task/phase/reviewer references in source.
- API contracts: every new endpoint's request/response Pydantic schema verified against the frontend Zod schema in the SAME commit.
- IPv4 in Vite proxy (unchanged from Phase 7).
- Vite proxy `/api/` prefix convention — route declarations updated to match.
- Decimal money discipline — unchanged.
- IST→UTC discipline — unchanged.

**Honest gaps documented:**
- No real auth. Session is anonymous; a determined attacker with another visitor's cookie value gets their session. Acceptable for a hiring demo; called out in README "Honest limitations."
- No email; no password reset; no user invites. Future work.
- Shopify real OAuth disabled on deployed — each visitor can't connect their own Shopify store. Demo data is the only Shopify path on the deployed URL.
- LLM cost: 50 concurrent reviewers chatting 5 times each = 250 LLM calls. Acceptable at current free-tier rate limits; called out in README.
- Render free tier cold start (~30s on first hit after 15min idle). Documented.
- SQLite on a 1 GB Render disk: ~10k merchants × 100 rows each = 1M rows. Comfortably within SQLite's limits but called out.

**Risk callouts:**
- The multi-stage Dockerfile's first build takes ~5-8 min on Render's free tier. Subsequent rebuilds with layer caching are faster but still slow.
- Frontend `dist` size affects Docker image size. Phase 7's 1MB pre-gzip is fine; if it grows, code-split.
- `SHOPIFY_OAUTH_ENABLED=false` must be honored EVERYWHERE on the frontend (the Connect button hides). If anyone adds another Shopify OAuth touchpoint, they need to read the env flag.
- `SessionMiddleware` stores session data inside the cookie itself. 4KB cookie limit. We only store two short strings (`merchant_id`, `user_id`); fits comfortably.

**Deferred to Phase 10 (if time permits):**
- Real email-based auth (magic link or password).
- Per-reviewer login links sent via email or pre-generated.
- WebSockets / SSE for chat streaming.
- Webhook ingestion for connectors.
- Load test harness `scripts/loadtest_visitors.py`.
