# Phase 13K Operations, Support Sessions and Completion QA Implementation Plan

> **For agentic workers:** execute task-by-task. Each task is failure-first: write or change the focused tests, run them and record the RED result, implement, run GREEN plus related suites, inspect the diff, then make the single task commit. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Wavia management area with audited, read-only, expiring support sessions and an honest operations-health view. Then prove the whole Studio with multi-role security, browser, accessibility and responsive regression suites and a final visual consistency pass. Stop for Hamzi's production review.

**Architecture:** FastAPI stays the authority. Support sessions are durable grants (migration 033) that a staff member opens from a tenant summary with a reason, a bounded read scope and a short expiry. Customer data is never read through tenant routes or a synthetic tenant header. Dedicated platform endpoints serve a safe projection of the tenant's configuration or readiness, only to the staff member who opened the session, only while it is active and only for granted scopes. Every start, end and read is written to the append-only platform audit. Operations health is a platform-admin snapshot built only from signals the control plane really has; anything not measured is labelled as such.

**Tech stack:** Python 3.12, FastAPI, Pydantic, psycopg async, PostgreSQL; Next.js 16, React 19, strict TypeScript, zod v4, Vitest, Playwright with `@axe-core/playwright`.

**Spec:** `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md` ("Support-access contract", "Data boundary", Phase 13K, "Verification strategy", "Success criteria"). **Prerequisite:** Phase 13J closed locally (`147a1d6`); Hamzi asked to start 13K on 2026-11-12. Nothing is pushed.

## Audit (2026-11-12)

| Area | Current state |
| :--- | :--- |
| Support access | None. Staff can read only the 13J safe directory and summary. |
| Tenant configuration readers | `control_plane/routes/agents.py` `get_agent_repo().list_agents(tenant)` returns full `AgentConfig` (persona prompt, tools, MCP endpoints, telephony). Knowledge bases: `get_default_knowledge_repository().list_knowledge_bases(tenant)` (metadata). |
| Readiness readers | Studio repository onboarding and entitlements; `telephony_settings_repository.get(tenant)` gives trunk and entitlement flags (`carrier_health` is always `unknown`). |
| Health signals | `/health` (static ok); `app.state.database` (present or in-memory); post-call jobs with states in `post_call_jobs`; `RUN_LIVE_PROVIDERS` / `RUN_LIVE_TELEPHONY` gates; OIDC provider configured or not; outbound runtime present or not; Prometheus registry behind a bearer. No live provider or carrier probe exists, and none may be added (H15). |
| Platform audit actions | Five 13J actions; `CHECK` constraint must be widened in 033. |
| Multi-role browser coverage | Per-feature journeys exist; there is no single matrix for the five customer roles plus two platform roles, no 320px pass and Axe only on the 13G pilot routes. |

## Global constraints

- Support sessions are **read-only**. No write scope exists. Any write scope needs a later explicit approval (spec "Human and safety gates").
- Scopes: `configuration` (safe agent and knowledge-base metadata) and `readiness` (setup progress, entitlements, telephony readiness flags). Transcripts, recordings, credentials, API keys, prompts, greetings, tool and MCP definitions are never returned.
- Duration: 15, 30 or 60 minutes. A reason of 8–500 characters is required; an optional reference (ticket ID) of at most 64 characters. At most one active session per staff member and tenant.
- Only the staff member who opened a session may read through it. Platform admins may end anyone's session; support staff may end only their own.
- An expired or ended session returns `410`; missing scope or another actor returns `403`; an unknown session returns `404`.
- New platform permissions (no wildcard):
  - `platform_admin`: `platform_support_session:read`, `platform_support_session:write`, `platform_support_session:manage`, `platform_operations:read`.
  - `platform_support`: `platform_support_session:read`, `platform_support_session:write`.
  Operations health stays admin-only at launch; support gets no operations subset yet (documented).
- Operations health never calls a live provider, carrier or identity provider and never shows secret values or environment-variable values, only whether something is configured.
- Studio keeps Theme B tokens and the shared primitives; no new runtime dependency; no colour literal outside `:root`.

## Review focus

- No path lets a support session read data after expiry, for another staff member, for an ungranted scope or for another tenant.
- Safe projections cannot leak prompt text, credentials or tool definitions (allowlist, not denylist).
- Every support read writes exactly one audit event, in the same request, before data is returned.
- Health labels never claim more than was measured.

## Rollback point

The plan commit is the checkpoint. Backend tasks (1–2) and Studio tasks (3–4) are separate atomic commits; QA tasks (5–6) add tests and presentation fixes only.

---

### Task 1: Support-session storage, permissions and repository (migration 033)

**Files:**
- Create: `infra/db/migrations/033_platform_support_sessions.sql`
  - `platform_support_sessions(session_id, actor_user_id → users, tenant_id → tenants, reason, reference, scopes TEXT[], created_at, expires_at, ended_at, ended_by, end_reason)` with checks on reason length, scope set, non-empty scopes, `expires_at` within 60 minutes of `created_at`, end fields consistent; partial unique index for one active session per actor and tenant is enforced in the repository (time-dependent).
  - Widen `platform_audit_events_action_check` with `platform_support.session_started`, `platform_support.session_ended`, `platform_support.data_viewed`; add nullable `support_session_id UUID` and `scope TEXT` columns with a scope check.
  - RLS enabled and forced, `REVOKE ALL FROM ucve_app`.
- Modify: `control_plane/auth/platform_rbac.py`, `control_plane/studio/models.py`, `control_plane/studio/repository.py`, `control_plane/studio/pg_repository.py`
- Create: `tests/auth/test_support_sessions.py`, `tests/db/test_phase13k_support_migration.py`, `tests/db/test_phase13k_live_support_sessions.py`

- [ ] Step 1: failing tests — permission matrix additions and no wildcard; start requires active staff, existing tenant, reason, scope subset and allowed duration; second active session for the same actor and tenant is rejected; end by owner, by admin, not by other support staff; authorize-read rejects expired, ended, other actor and missing scope, and audits exactly once on success; list is bounded; live DB: constraints, audit widening, `ucve_app` denied, expiry evaluated by the database clock.
- [ ] Step 2: RED.
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Python suite; disposable PostgreSQL 13H/13J/13K live files.
- [ ] Step 5: commit `feat(platform): add audited read-only support sessions`

### Task 2: Support-session and operations API

**Files:**
- Modify: `control_plane/routes/platform.py`
  - `POST /v1/platform/tenants/{tenant_id}/support-sessions` (`platform_support_session:write`)
  - `GET /v1/platform/support-sessions?state=active|recent&limit=` (`platform_support_session:read`)
  - `GET /v1/platform/support-sessions/{session_id}` (`platform_support_session:read`)
  - `POST /v1/platform/support-sessions/{session_id}/end` (`platform_support_session:write`; others' sessions need `:manage`)
  - `GET /v1/platform/support-sessions/{session_id}/configuration` and `/readiness` (owner, active, scope)
  - `GET /v1/platform/operations` (`platform_operations:read`)
- Create: `control_plane/platform/support_views.py` (allowlisted projections), `control_plane/platform/operations.py` (health snapshot)
- Modify: `post_call/jobs/repository.py` (`count_jobs_by_state()` for both repositories)
- Create: `tests/auth/test_platform_support_routes.py`, `tests/auth/test_platform_operations.py`

- [ ] Step 1: failing tests — route matrix for every new route (unauthenticated 401, API key 401, tenant header 400, customer 403, wrong staff 403, expired/ended 410, missing scope 403, unknown 404); projections exclude prompt, greeting, tools, MCP, credentials and telephony trunk details (allowlist test against a fully populated agent); each read writes one `platform_support.data_viewed` event with the scope; operations snapshot reports in-memory vs database honestly, job counts, live gates off, provider and carrier health "not measured"; support gets 403 for operations; every `/v1/platform/*` route is covered by a platform dependency (route-table completeness test).
- [ ] Step 2: RED.
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Python suite.
- [ ] Step 5: commit `feat(control-plane): add support session and operations api`

### Task 3: Studio support sessions

**Files:**
- Modify: `studio/src/data/schema.ts`, `studio/src/auth/platform-permissions.ts`, `studio/src/features/admin/{data,actions,types}.ts`, `admin-navigation.tsx`, `tenant-summary-view.tsx`, `studio/e2e/fixtures/offline-auth-server.mjs`, `globals.css`
- Create: `studio/src/app/(admin)/admin/support-sessions/page.tsx`, `[sessionId]/page.tsx` (+ loading/error), `studio/src/features/admin/support-session-*.tsx`
- Create: `studio/tests/admin-support-sessions.test.tsx`; extend `studio/e2e/platform-admin.spec.ts`

- [ ] Step 1: failing tests — "Start support session" on the tenant summary opens a form dialog (reason, optional reference, scope checkboxes, duration select) and is absent without `platform_support_session:write`; the session page shows a persistent banner with tenant, "Read-only" and the UTC end time, plus an **End session** action; only granted scope sections render; expired or ended sessions show an honest state and no data; list page shows active and recent sessions with end controls according to ownership and `:manage`; navigation adds "Support sessions" by capability.
- [ ] Step 2: RED — `npm.cmd test -- admin-support-sessions.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Studio unit suite; support-session Chromium journey (start → view → audit shows reads → end → data gone).
- [ ] Step 5: commit `feat(studio): add audited support sessions`

### Task 4: Studio operations health

**Files:** `studio/src/app/(admin)/admin/operations/page.tsx` (+ loading/error), `studio/src/features/admin/operations-view.tsx`, schema, data, navigation, fixture, `globals.css`, `studio/tests/admin-operations.test.tsx`, `platform-admin.spec.ts`

- [ ] Step 1: failing tests — admin-only route and navigation item; each signal shows a text status badge (Healthy, Not configured, Disabled, Not measured, Attention) never colour-only; job state counts; live gates shown as disabled with the reason; snapshot time in fixed UTC; support redirected.
- [ ] Step 2: RED.
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; operations Chromium journey.
- [ ] Step 5: commit `feat(studio): add platform operations health`

### Task 5: Multi-role security, accessibility and responsive regression

**Files:** Create `studio/e2e/role-matrix.spec.ts`, `studio/e2e/accessibility.spec.ts`; extend `phase13h-shell-qa.spec.ts` (320px); `tests/auth/test_route_matrix.py` additions if gaps are found.

- [ ] Step 1: failing or new tests — for each customer role (admin, editor, developer, viewer, compliance) the exact navigation items and that each forbidden route redirects with the forbidden message; for platform support and admin the exact internal navigation and denials; customers cannot reach `/admin`; staff without memberships see no workspace; Axe (WCAG 2.1 A/AA tags) reports no serious or critical violations on every customer and admin route; every route has no horizontal overflow at 320px; `prefers-reduced-motion` disables shell transitions.
- [ ] Step 2: RED — record any real failures.
- [ ] Step 3: fix product defects found (presentation or authorization), never weaken a test.
- [ ] Step 4: GREEN; full Chromium suite.
- [ ] Step 5: commit `test(studio): add multi-role, accessibility and 320px regression`

### Task 6: Final visual consistency pass

**Files:** presentation-only fixes in `studio/src/**` and `globals.css`; captures under gitignored `hamza_local/phase13k-qa/`.

- [ ] Step 1: capture every customer and admin route at 1280px, 390px and 320px.
- [ ] Step 2: review for spacing, heading rhythm, badge/notice consistency, empty/loading/error states, table/card parity, truncation and focus visibility; list findings.
- [ ] Step 3: fix; re-capture; unit and Chromium suites stay green.
- [ ] Step 4: commit `style(studio): final visual consistency pass`

### Task 7: Phase 13K close gate — stop for production review

**Files:** `Codex Fix/evidence/phase-13k/{PROGRESS,VERIFICATION}.md`, `Codex Fix/EXECUTION_TRACKER.md`, `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md`, `docs/design-system/project-profile.md`

- [ ] Step 1: full forced-offline Python suite, ruff, mypy on changed modules, plan integrity.
- [ ] Step 2: disposable PostgreSQL — all `tests/db` from empty; teardown verified.
- [ ] Step 3: Studio unit, typecheck, lint, production build, full Chromium.
- [ ] Step 4: scans — no wildcard, no support write path, projections allowlisted, inline style/colour, protected paths, secret signatures, client bundle, `git diff --check`.
- [ ] Step 5: evidence and tracker; label Safari, physical devices, screen readers, forced colours, Lighthouse/Core Web Vitals, live WorkOS/MFA, live providers and Telnyx as unverified.
- [ ] Step 6: commit `test(platform): close phase 13k operations and support`, then stop for Hamzi's production review (Phase 14 does not start automatically).
