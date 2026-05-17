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

## 2026-05-17 — persistent chat suggestions + thinking indicator

**What changed:** Two cosmetic touches in `apps/web/src/modules/chat/components/MessageList.tsx`.

- Suggestion chips no longer disappear after the first message. They render below the message list with a "Try also:" label, smaller / pill-shaped, horizontally scrollable. The empty-state still surfaces them as larger buttons.
- The pending typing indicator now shows a cycling phrase line under the bouncing dots — "Looking up your data…" → "Cross-referencing shipment history…" → "Composing answer…" — rotating every 1.5s. AnimatePresence with `mode="wait"` handles the fade.

**Why:** Cosmetic but agentic. The chat agent is real (LLM + tools), but during the 2–5s wait the UI gave no signal. Cycling status phrases make the wait feel like reasoning, not loading. The persistent chips lower the friction of "what do I ask next" once the user has used the first prompt.

**Important non-claim:** the phrases are NOT tied to the actual tool calls. We do not stream the LLM's tool-call events to the frontend in v0; integrating that would be a real feature. Per the brief, this is cosmetic only.

**Files touched:** `apps/web/src/modules/chat/components/MessageList.tsx`.

**Reverts cleanly?:** yes.

---

## 2026-05-17 — records page — IST dates, source chips, friendly labels

**What changed:** The records table moves from "ISO blob + raw lowercase source string + 50-row cap" to a legible, filterable view.

- Backend `list_endpoint` default limit: 50 → 200 (one-line bump, same `le=200` cap). At ~96 demo rows, the first page now shows every row; without the bump, a fresh Shiprocket sync's 50 newest-fetched rows pushed Shopify + Meta below the fold.
- New `apps/web/src/shared/utils/fmtIST.ts` — IST renderer (en-IN locale, Asia/Kolkata, 12-hour). Used in the records table; can be reused in run detail later. Raises on invalid input rather than silently rendering a placeholder.
- Source filter chips (All / Shopify / Meta Ads / Shiprocket) drive a query param; chips and the records query key are typed via the new `RecordsSourceFilter` `as const` enum.
- Source column: friendly label + colored dot (lavender / pop / success — existing tokens, no new colors). Entity column: `order` → "Order", `shipment` → "Shipment", `ad_spend` → "Ad spend".
- Empty state for a fresh `/auth/start`-but-no-`/auth/onboard` workspace: "Your demo workspace is empty. Run onboarding to load demo data." + button → `/onboarding`. Required extending `EmptyState` with an optional `action` prop.
- Honest cap line at the bottom: when 200 rows render, "Showing first 200 of your records — sync filtering coming soon."
- `RECORDS_LIST_QUERY_KEY` became a function of the filter; `useSyncMutation` now invalidates the bare `['records']` prefix so every variant refetches.

**Why:** Phase 7 left the records page as a developer tool. With the chat citation contract reading from this table, a reviewer who clicks into Records gets a first impression of the whole data model — if it looks like a debug log, the trust on every grounded number drops. Friendly labels + IST + filter chips raise the bar to "I'd hand this to a merchant."

**Files touched:** `apps/api/src/munim/modules/records/router.py`, `apps/web/src/shared/utils/fmtIST.ts` (new), `apps/web/src/shared/components/EmptyState.tsx`, `apps/web/src/modules/records/{api/records.api.ts,hooks/useRecords.ts,types/record.types.ts,components/RecordsTable.tsx,components/RecordsPage.tsx,index.ts}`, `apps/web/src/modules/connectors/hooks/useSyncMutation.ts`.

**Reverts cleanly?:** yes.

---

## 2026-05-17 — onboarding wizard with animated demo seed

**What changed:** The demo-data opt-in moves from "silently pre-seeded by `/auth/start`" to "explicit step in the onboarding wizard."

- Backend: `POST /auth/start` no longer calls `seed_new_merchant`. New `POST /auth/onboard` runs the same seed and returns `{shopify_rows, meta_ads_rows, shiprocket_rows}` (typed `OnboardingResult`). The result reflects rows the merchant OWNS post-seed, not the upsert delta of the last call — so a re-run from a bookmark shows the same numbers.
- Frontend: new `/onboarding` route (ProtectedRoute-wrapped). `OnboardingPage.tsx` calls the onboard mutation, then animates each of the three connector cards in sequence (~700ms apart) for an agentic feel. Idempotency: on mount, if `useConnectors()` reports all three sources as `status === 'demo'` with non-null `last_sync_at`, the page jumps straight to the success view. CTA flips to a "Go to chat →" link when all cards are green.
- `StartPage` redirect after `/auth/start` is now `/onboarding`, not `/chat`.
- `auth_client` test fixture posts `/auth/start` + `/auth/onboard` so existing protected-endpoint tests continue to see the 96 seeded rows; tests that need an empty workspace use the anonymous `client` fixture.
- Five new auth-router tests: `start` does not pre-seed; `onboard` returns correct counts; `onboard` is idempotent; `onboard` returns 401 without a session.

**Why:** A reviewer landing on /start expects to choose whether to load demo data. Silent pre-seeding hides the connectors story (the brief's third axis) behind a request the user didn't make. The wizard surfaces the three connectors visually, makes the seed legible, and gives the demo a first-impression moment.

**Files touched:** `apps/api/src/munim/modules/auth/{router,seed,schemas}.py`, `apps/api/src/munim/modules/auth/tests/test_router.py`, `apps/api/conftest.py`, `apps/web/src/pages/OnboardingPage.tsx`, `apps/web/src/router.tsx`, `apps/web/src/modules/auth/{api/client.ts,hooks/useAuth.ts,index.ts,components/StartDemoForm.tsx}`.

**Reverts cleanly?:** yes.

---

## 2026-05-17 — shopify demo sync loads package fixture, last_sync_at stamps

**What changed:** Two coupled bug fixes that landed Phase 9's Shopify demo path on the same shape Meta and Shiprocket already used.

- `ShopifyClient._iter_demo_orders` now reads `apps/api/src/munim/connectors/shopify/fixtures/orders.json` from a hardcoded package path. The credential blob's `fixture_path` is no longer required (or read).
- `seed.py::_seed_demo_connector` now drives all three connectors (Shopify, Meta, Shiprocket) through `connector.sync_full`, and stamps `credential_row.last_sync_at` after each successful run. The old `_seed_shopify` direct-to-RowSink path is gone.
- `service.py::connect_demo` drops `fixture_path` from the Shopify blob it writes; the legacy `_resolve_demo_fixture_path` helper is removed (dead).
- New test `test_shopify_demo_sync_uses_package_fixture` locks the contract. Existing connector tests migrated from 3-row to 6-row expectations.

**Why:** Phase 9's seed wrote `{"status": "demo"}` only, but Phase 2's client demanded `fixture_path` in the blob → "Sync now" failed for every new visitor. Also: the direct-to-RowSink seed never stamped `last_sync_at`, so the UI's "Synced N seconds ago" was permanently empty. The root cause is documented in `context.md` (2026-05-17 entry, Problems & solutions).

**Files touched:** `apps/api/src/munim/connectors/shopify/client.py`, `apps/api/src/munim/modules/auth/seed.py`, `apps/api/src/munim/modules/connectors/service.py`, plus the Shopify connector / client / service / router test files.

**Reverts cleanly?:** yes.

---

## 2026-05-16 — Phase 9 review fixes

**What changed:** Reviewer surfaced 4 CRITICAL + 12 IMPORTANT findings; all CRITICAL and the actionable IMPORTANT items addressed in one fix commit.

- **`render.yaml` autoDeploy → false** so a bad commit cannot auto-publish to the live URL during the final sprint. A reviewer must explicitly click "Deploy latest commit" in the Render dashboard.
- **Backend `SHOPIFY_OAUTH_ENABLED` flag now enforced server-side** — `start_oauth` and `complete_oauth` raise the new `FeatureDisabledError` (HTTP 403, `feature.disabled`) when the flag is false. The flag was honored on the frontend only; the deployed backend was leaking real Shopify authorize URLs built from placeholder client ids. New `ErrorCode.FEATURE_DISABLED` registered + tests cover both endpoints.
- **`FRONTEND_BASE_URL` declared in `render.yaml`** (sync: false, user-managed post-deploy) so future post-OAuth redirects don't silently fall back to `localhost:5173`.
- **Sidebar surfaces `user.display_name`** (avatar with initials + name + "Demo workspace" subtitle) and a wired Sign-out button. The reviewer flagged that the input on `/start` was never displayed and `useLogout` was exported but never called from the UI; both fixed.
- **Auth tests strengthened**: the original tampered-signature test stays as the proof that signed-cookie verification runs; added a positive cookie-portability test that confirms a valid cookie carries identity across two `TestClient` instances. Together they lock the contract "HMAC verification is the gate, not cookie presence."

**Deferred** (deliberately, with rationale in context.md):
- `DEFAULT_MERCHANT_ID` redeclared in 8 test files instead of imported. NIT-level §7 violation; sed sweep not worth the time pressure.
- `auth_blob_encrypted` column name misleading for demo rows. Pre-existing from Phase 4; Phase 10 cleanup.
- `useAuthContext` colocated with `<AuthProvider>` + local eslint-disable. Refactor opportunity, not blocking.
- Middleware-order docstring clarification. Cosmetic.

**Test counts:** 235 → 238. All gates green: `ruff` + `ruff format` + `mypy` + `pytest` (backend) and `pnpm typecheck` + `pnpm lint` + `pnpm build` (frontend).

**Deploy verdict:** reviewer flipped from "NOT YET safe to deploy publicly" to ready-to-deploy with these fixes.

---

## 2026-05-16 — Phase 9 multi-tenant backbone + deployment

**What changed:** Phase 9 closes the brief's remaining gap — the scaling claim moves from "future-tense paragraph" to "tested property of the running system." Every visitor to the deployed URL gets a fresh `Merchant` + `User` row, a signed anonymous session cookie, and 96 pre-seeded demo rows isolated from every other visitor.

- **Anonymous session cookie via starlette `SessionMiddleware`** — HMAC-signed cookie (itsdangerous), `same_site="lax"`, 30-day max-age. Carries `{merchant_id, user_id}`.
- **`POST /auth/start`** mints `Merchant` + `User`, seeds 96 demo rows synchronously (6 Shopify orders + 40 Meta insights + 50 Shiprocket shipments), sets the cookie, returns `CurrentUser`. **`GET /auth/me`** returns the current user (401 with `auth.unauthenticated` if no session). **`POST /auth/logout`** clears the session.
- **`get_current_merchant_id` FastAPI dependency** — typed 401 `UnauthenticatedError` when the session is missing. NO silent fallback to a default merchant.
- **Every router refactored.** Connectors, records, chat, agents now read `merchant_id` via `Depends(get_current_merchant_id)`. `DEFAULT_MERCHANT_ID` stays in `shared/db.py` as a TEST-ONLY constant; `init_db` no longer auto-creates it.
- **Shopify fixture for Phase 9 demo** — `apps/api/src/munim/connectors/shopify/fixtures/orders.json` — 6 real-shape Shopify orders with customer emails matching the Shiprocket fixture's curated customers, so the cross-connector hash join lands immediately on first agent run.
- **Frontend:** new `AuthProvider` + `ProtectedRoute` + LandingPage + StartPage. `ky` now ships `credentials: 'include'` so the signed cookie rides every request. Connectors page hides the real Shopify Connect button when `VITE_SHOPIFY_OAUTH_ENABLED !== 'true'`. Phase 8 cleanup: dead `useConnectMutation` + `postConnect` deleted; `ConnectorsGrid`'s silent `return null` replaced with `<EmptyState>`.
- **All FastAPI routers now mount under `/api`.** Dev and prod URLs match without conditional logic. The Vite dev proxy stops stripping `/api`; `SHOPIFY_OAUTH_REDIRECT_URI` updated to `/api/connectors/shopify/oauth/callback`.
- **Deployment:** multi-stage `Dockerfile` (Node 22 alpine builds the SPA; Python 3.11 slim runs uvicorn + serves the dist as static). `render.yaml` declares a `web` service with a 1GB persistent disk at `/data` and auto-generated `SESSION_SECRET`/`CREDENTIALS_ENCRYPTION_KEY`. Local `docker build -t munim:phase9 . && docker run -p 18000:8000 ...` succeeds; both `/api/health` and `/api/auth/start` work in the container.
- **`auth_client` conftest fixture** — new TestClient pre-seeded with a fresh session cookie via `POST /api/auth/start`. Existing protected-endpoint tests migrated; each module gets one unauthenticated-path test (401) plus isolation spot-checks on records, connectors, and agent-runs.
- **Architecture §10 rewritten.** Multi-tenant moves from rank 6 ("v0 has no auth") to rank 6 with concrete Phase 10 description; sync orchestration moves to rank 1; "what we built to absorb the future" is reframed as tested behaviour.
- **README rewritten.** Live-demo link, four-bullet citation contract, four-bullet agent description, honest-limitations section, tech-choices defenses.

**Why:** The brief's "≥10k merchants" scalability story was the last gap — the rest of the system already had `merchant_id` on every row, but a reviewer reading the docs had to take it on faith. Phase 9 turns that into a property the reviewer can verify by opening an incognito window: each visitor is a real merchant, isolation is tested, and the Postgres migration is one config change.

**Files touched:** `apps/api/src/munim/models/user.py` (new), `apps/api/src/munim/modules/auth/**` (new), `apps/api/src/munim/main.py` (SessionMiddleware + /api prefix + static mount), `apps/api/src/munim/modules/{connectors,records,chat,agent_runs}/router.py` (Depends), `apps/api/src/munim/shared/{config,constants,db}.py`, `apps/api/conftest.py` (auth_client fixture), `apps/web/src/modules/auth/**` (new), `apps/web/src/pages/{LandingPage,StartPage}.tsx` (new), `apps/web/src/{main,router,shared/api/client}.tsx?`, `Dockerfile` + `render.yaml` + `.dockerignore`, `docs/architecture.md` §10, `README.md`.

**Reverts cleanly?:** yes. The session cookie is additive — removing the auth router + dependency would leave the rest of the multi-tenant code intact (it would just always read `DEFAULT_MERCHANT_ID`). The `/api` prefix change is a one-line rollback in `main.py` + the Vite proxy + every test path.

---

## 2026-05-15 — Phase 8 review fixes + cross-connector smoke

**What changed:** Reviewer surfaced 4 CRITICAL + 9 IMPORTANT findings; all CRITICAL and the actionable IMPORTANT items addressed in one fix commit.

- **Customer hash extracted** to `shared/utils/customer_hash.py` (was Shopify importing from Shiprocket — package coupling). Empty-string email/phone normalised to None at entry so the two upstream conventions ("missing=None" vs "missing=''") produce identical hashes for the same human.
- **Legacy `/connect` endpoint now rejects Phase 8 demo connectors** with `LegacyConnectRejectedError` (HTTP 400, `connector.not_demo`). Shopify still works through this path for pre-Phase-4 test setups; the two endpoints are now complementary instead of overlapping.
- **`cpm` → `cpm_inr` Decimal** in `MetaAdSpend`. CPM is INR-per-thousand-impressions; float would bleed once a chat query multiplies by impressions to recover spend (§8.1).
- **Three regression tests added:** `MissingShipmentFieldError` raise path (was raised but never proven to fire — Phase 3 dead-code lesson regression); `customer_rto_rate` saturation cap at 1.0 for pure-RTO history; customer C 1/5 RTO distribution in the Shiprocket fixture (was locking A and B only).
- **Shiprocket mapper tz-aware handler softened** — was raising on offset timestamps (locked the wrong invariant — would fail if Shiprocket fixed their API). Now converts to UTC normally.
- **`ConnectorCard.tsx` magic string fixed** — replaced `view.name === 'shiprocket'` with `ConnectorName.Shiprocket` constant. Dropped redundant `as ConnectorName` casts.
- **`apps/api/scripts/seed_cod_order.py` rewritten** to seed two COD orders (Customer A high-RTO + Customer B clean) whose `customer_source_id` hashes match the Shiprocket fixture's curated customers — the cross-connector join now demonstrates the agent narrative end-to-end.

**Live smoke walk (verified):**
- `POST /connectors/meta_ads/connect-demo` → status `demo`, no creds stored encrypted.
- `POST /connectors/meta_ads/sync` → 40 ad_spend rows upserted.
- `POST /connectors/shiprocket/connect-demo + sync` → 50 shipment rows upserted.
- `POST /connectors/meta_ads/connect` (legacy) → 400 `connector.not_demo` with helpful body pointing to `/connect-demo`.
- Re-seed COD orders → `POST /agents/rto_mitigator/run` produces 3 decisions:
  - `seed_cod_high_risk` (Customer A, 3/5 RTO via Shiprocket) → `convert_to_prepaid` score 0.772, est ₹3242.40 saved.
  - `seed_cod_clean` (Customer B, 0/5 RTO) → `confirmation_call` score 0.409, est ₹981.60.
  - `seed_cod_demo` (no Shiprocket history) → population baseline 0.2 → `convert_to_prepaid` score 0.618.

**Test counts:** 206 → 213 backend (+7). `pnpm typecheck && pnpm lint && pnpm build` all green.

**Deferred to Phase 9 cleanup (documented):** `useConnectMutation` + `postConnect` dead code; `ConnectorsGrid` silent-null on empty registry; `auth_blob_encrypted` column name now misleading for demo rows.

**Reverts cleanly?:** Yes — single fix commit on top of Phase 8.

---

## 2026-05-15 — Phase 8: Meta Ads + Shiprocket demo connectors

**What changed:** Brought the project to three connectors behind one `BaseConnector` ABC (the brief's hard requirement) by adding Meta Ads and Shiprocket as demo-mode connectors alongside the real Shopify OAuth path. Curated Shiprocket shipment fixture so the RTO agent's customer-history signal fires meaningfully on the demo (high-RTO customer A → `convert_to_prepaid`, clean customer B → `no_action`). Rewired `customer_rto_rate` to read shipments instead of orders (orders never carry `fulfillment_status` — that's a shipment lifecycle attribute), and migrated the Shopify mapper's `customer_source_id` from raw Shopify ID to SHA-256(email||phone) so the cross-connector join works.

- **Backend connector packages:**
  - `connectors/meta_ads/` — `mapper.py` (raw Meta `/insights` row → typed `MetaAdSpend`), `connector.py` (`MetaAdsConnector(BaseConnector)`, `is_demo=True`, 200 ms sleep), `fixtures/insights.json` (40 rows = 4 D2C-realistic campaigns × 10 days; spend distribution skewed by funnel stage; CTR/CPM/ROAS plausible).
  - `connectors/shiprocket/` — `mapper.py` (raw Shiprocket `/v1/external/orders` row → typed `Shipment` with IST-naive `created_at` → UTC conversion at the boundary, status enum sweep, customer-hash), `connector.py` (`ShiprocketConnector(BaseConnector)`, `is_demo=True`, 200 ms sleep), `fixtures/shipments.json` (50 rows: customer A 3 RTO + 2 DELIVERED, customer B 5 DELIVERED, customer C 1 RTO + 4 DELIVERED, ~35 scatter rows).
- **`BaseConnector.is_demo`** — new ClassVar; defaults False, both new connectors override True. Threaded through `ConnectorView.is_demo` on the API response.
- **`POST /connectors/{name}/connect-demo`** — generic demo-connect endpoint. Validates connector exists and `is_demo`, upserts credentials row with `status=DEMO` and empty blob, returns the view. Wrong-connector cases: `connector.unknown` (404) for unknown name, `connector.not_demo` (400) for Shopify and any future non-demo connector. New `ErrorCode.CONNECTOR_NOT_DEMO` registered + raised.
- **RTO agent rewire** — `customer_rto_rate` now queries `record` where `source_system=shiprocket` and `entity_type=shipment`. Joins on `customer_source_id`. The Shopify mapper hashes `customer.email` (preferred) or `customer.phone` (fallback) with the same algorithm as the Shiprocket mapper so the same human matches across both. `customer_source_id` becomes None for guest checkouts with no email + no phone (existing test covered this; still works).
- **Frontend** — Zod schema picks up `is_demo`. `useConnectDemoMutation` + `EnableDemoButton` (toasts "Demo data enabled for {name} — click Sync to load"). `ConnectorCard` branches: real connector + not connected → existing "Connect to your store" OAuth button; demo connector + not connected → `EnableDemoButton`; either + connected → existing "Sync now". "demo" badge surfaces alongside the status badge so the UI is honest about which connector is fixture-backed. Per-row count label adapts: shipments for Shiprocket, ad-spend for Meta, orders for Shopify.

**Why:** The brief's hard requirement is ≥3 connectors behind one abstraction; Shopify alone wasn't going to land that. Meta and Shiprocket as demo-mode is the honest scope call (Shiprocket has no public sandbox, Meta's OAuth would burn 30-60 min of reviewer setup with zero payoff if the eval account has no spend). Real-mode swap is mechanical: replace `_load_fixture` with HTTP-calling iterators, no abstraction change. The RTO agent rewire fixes a pre-existing latent bug — order rows never carry `fulfillment_status` (because fulfillment is a shipment attribute), so the customer-history signal silently returned the population baseline for every customer in Phase 6. With Shiprocket data + the rewire, the signal now does what it was designed to do.

**Files touched:**
- `apps/api/src/munim/connectors/{meta_ads,shiprocket}/**` (new)
- `apps/api/src/munim/connectors/base.py` (`is_demo`)
- `apps/api/src/munim/connectors/registry.py` (register new connectors)
- `apps/api/src/munim/connectors/shopify/mapper.py` (`_extract_customer_id` → SHA-256 hash)
- `apps/api/src/munim/modules/connectors/{demo_connect.py,router.py,service.py,schemas.py}` (new endpoint + `is_demo` field)
- `apps/api/src/munim/agents/rto_mitigator/signals.py` (`customer_rto_rate` reads shipments)
- `apps/api/src/munim/shared/constants.py` (`ErrorCode.CONNECTOR_NOT_DEMO`, `FulfillmentStatus.IN_TRANSIT`)
- `apps/web/src/modules/connectors/**` (Zod schema, `useConnectDemoMutation`, `EnableDemoButton`, `ConnectorCard` branch)

**Reverts cleanly?:** Yes — purely additive on the backend (the Shopify mapper customer-id change is the only behavioural diff, and the schema is backward-compatible). Removing the new connectors is one `registry.py` line and one folder per side. Frontend is a clean module update.

**Test counts:** 168 → 206 backend tests (+38). `pnpm typecheck && pnpm lint && pnpm build` all green.

---

## 2026-05-15 — Phase 7 review fixes

**What changed:** Reviewer subagent surfaced 4 CRITICAL + 9 IMPORTANT findings; all addressed.

- **Chat was broken end-to-end** — the Phase 7 plan had the wrong contract baked into its code blocks (request body `prompt` instead of `message`; response shape `used_citations`/`available_citations`/`id` instead of `citations`/`record_id`). Implementer copied it faithfully. Backend never changed. Fixed `apps/web/src/modules/chat/api/client.ts` Zod schemas to match the actual backend `ChatMessageRequest`/`ChatMessageResponse` (Phase 5). Propagated rename through `useChat`, `MessageBubble` (citation lookup by `record_id`), `CitationBadge` (render `record_id`).
- **Tooltip Provider** was nested INSIDE `Tooltip.Root` instead of being an ancestor — every citation badge tooltip silently failed. Hoisted `TooltipProvider` to `main.tsx` ancestor; simplified `Tooltip` export to `TooltipPrimitive.Root`.
- **ActionDonut** had three hardcoded light-mode HSL strings (`hsl(263 70% 60%)` etc.), so the chart rendered with wrong colors in dark mode. Now reads CSS custom properties at render time and re-keys off `useThemeStore.resolvedTheme`.
- **trace_id never surfaced in error UI** — added `error.traceId` rendering to ChatPage, RunsTable, RunDetailSheet, useTriggerAgent toast. Now any "the chat failed" report carries the grep-able trace id.
- **Citation parser dropped empty inline-flex spans** for hallucinated ids — fixed parser to filter cite-token ids by whether they exist in the response citations and skip the entire token when none resolve.
- **Double toast on manual trigger** — added `useAgentRunMetaStore` (Zustand) so `useAgentNudges` skips its toast when newest run_log_id === the id `useTriggerAgent` just wrote. Single toast on the demo's headline interaction.
- **Inline `formatINR` with silent fallback** — extracted to `shared/utils/inr.ts` that throws `InvalidMoneyError` on non-finite; `RunDetailSheet` boundary renders `—` on catch.
- **Magic string `'rto_mitigator'`** — added `shared/constants/agents.ts` with `AgentName` `as const`; mirrors the backend StrEnum.
- **Module index.ts** added for chat, agent_runs, feed (§3.2 public surface).
- **Row click keyboard-accessible** — RunsTable rows now have `tabIndex={0}`, `role="button"`, `onKeyDown` for Enter/Space.
- **Avatar double-styling** removed from `MessageBubble` + `MessageList` (Fallback owns the bg-accent; root just sizes).

**Deferred (NIT, documented in context.md):** ErrorBoundary at root; recharts/sonner major-version bump notation; `fmtIST()` helper (timestamps still use browser locale); bundle code-split for Recharts; connectors page polish.

**Live API smoke (chat contract):** `POST /chat/messages` with `{ message: "How many orders do I have total?" }` returned `{ text: "You have a total of 4 orders[cite:4,3,2,1].", citations: [4 records] }` matching the new Zod schema exactly. trace_id propagated.

**Reverts cleanly?:** yes — single fix commit on top of Phase 7.

---

## 2026-05-15 — Phase 7 frontend shell + chat + agent runs

**What changed:** Shipped the frontend for the two scored axes of the brief plus the polished shell that contains them.
- **Lavender token system** rewritten in `globals.css`: light + dark, expanded scale (surface / surface-elevated / surface-subtle / sidebar-* / fg / fg-muted / fg-subtle / border / border-strong / ring / primary / primary-hover / accent / pop / success / warning / destructive), rounded radii (md=14px, lg=20px, xl=28px). Legacy aliases (`muted`, `error`, `bg-subtle`) mapped to new tokens so the migration didn't have to be atomic.
- **shadcn-style UI primitives** in `shared/ui/`: Button (cva variants: primary/secondary/ghost/destructive/pop), Card + Header/Title/Description/Content, Sheet (Radix Dialog as side drawer), ScrollArea, Avatar, Badge, Separator, Tooltip, Skeleton, Toaster (Sonner). All on Radix headless + Tailwind v4 + `tw-animate-css` for the sheet's `data-state` animation classes.
- **App shell** in `shared/layout/`: 3-column grid (Sidebar 248px + Main + FeedPanel 360px) with framer-motion page transitions. Sidebar has dark surface, icon nav with animated active indicator (`layoutId` shared transition), and a theme cycle button (light → dark → system).
- **`/chat`** — POST `/chat/messages`, citation badges parsed inline from `[cite:N]` markers, hover Tooltip shows source_id + entity_type, avatar persona, typing indicator while pending, empty state with 4 suggestion chips.
- **`/agents`** — table of runs with TriggerAgentButton, ?run=<id> opens a detail sheet with action distribution donut (Recharts), per-order decisions (signal scores, INR saved, full reasoning).
- **FeedPanel** — `useAgentNudges` polls `GET /agent-runs?limit=10` every 30s, NudgeCards render the last 10 runs, Sonner toast fires on new arrivals with a Review action that deep-links to the agent run.
- **Connectors + Records** light migration: pages now wrap content in `fadeUp` motion, legacy `text-muted` / `text-error` / `bg-bg-subtle` rewritten to the new tokens, internal logic untouched.
- **Router**: `/` → redirect to `/chat`; `/chat`, `/agents`, `/connectors`, `/records` under the new AppShell. Old IndexPage and `shared/components/{AppShell,NavLink}` deleted.

**Why:** The brief is graded half on craft, half on judgment. The chat surface (with citations) and the agent runs surface (with the deterministic-reasoning audit log) are the two scored axes; both shipped behind a shell that looks like a product, not a demo.

**Files touched (load-bearing):**
- `apps/web/src/styles/globals.css`
- `apps/web/src/shared/ui/*` (10 new files + barrel)
- `apps/web/src/shared/layout/{AppShell,Sidebar,FeedPanel}.tsx`
- `apps/web/src/shared/utils/{cn,motion}.ts`
- `apps/web/src/modules/chat/**` (api/client, hooks/useChat, components/CitationBadge|MessageBubble|MessageList|ChatInput, ChatPage)
- `apps/web/src/modules/agent_runs/**` (api/client with Zod schemas mirroring backend StrEnum, hooks/useAgentRuns|useAgentRun|useTriggerAgent, components/RunsTable|RunDetailSheet|ActionDonut|TriggerAgentButton, AgentRunsPage)
- `apps/web/src/modules/feed/**` (hooks/useAgentNudges with sonner toast, components/NudgeCard|NudgeFeed)
- `apps/web/src/router.tsx`, `apps/web/src/main.tsx` (Toaster mount)
- `apps/web/package.json`: +`framer-motion`, `recharts`, `sonner`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, 7 Radix headless packages

**Reverts cleanly?:** yes — all changes are scoped to `apps/web/` and the legacy components (`Button.tsx`, `Card.tsx`) were retained alongside the new primitives, so no cascading downstream breakage.

**Honest gaps documented:**
- No streaming chat (typing indicator covers the latency).
- No chat history persistence (stateless per Phase 5 Option A).
- No mobile layout (desktop-first; feed panel hides below 1024px, sidebar collapses no further).
- Component tests minimal — Zod boundary validation + manual smoke is the v0 gate.
- `useAgentNudges` toast fires on every new `run_log_id` during polling, including ones the user triggered themselves. Acceptable for v0; dedupe pass deferred.

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
