# Phase 13J Platform Management Security Foundation Implementation Plan

> **For agentic workers:** execute task-by-task. Each task is failure-first: write or change the focused tests, run them and record the RED result, implement, run GREEN plus related suites, inspect the diff, then make the single task commit. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invisible `platform_admin: {"*"}` wildcard with two durable, explicitly enumerated platform staff roles (`platform_admin`, `platform_support`). Give them a dedicated, non-tenant authorization path and a lean internal Studio area (`/admin`) for a bounded tenant directory, safe tenant detail, staff management and platform audit.

**Architecture:** FastAPI stays the authorization authority. Platform staff roles live in a new `platform_memberships` table; the old `users.is_platform_admin` flag is migrated once and no longer read for authorization. Platform routes use a separate `require_platform_permission` dependency that accepts only OIDC identities and refuses tenant context. Tenant routes no longer recognise any platform role. Studio adds an `(admin)` route group with its own layout, navigation and server-only data layer, driven by platform capability strings returned from `/v1/me`.

**Tech stack:** Python 3.12, FastAPI, Pydantic, psycopg async, PostgreSQL with RLS; Next.js 16 App Router, React 19, strict TypeScript, zod v4, Vitest, Playwright offline fixture.

**Spec:** `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md` (sections "Platform staff roles", "Wavia management area", "Backend changes", Phase 13J). **Prerequisite:** Phase 13I closed locally (`a049602`); Hamzi asked to start 13J on 2026-11-12. Nothing is pushed until the whole program is complete.

## Audit (2026-11-12)

| Area | Current behavior | Risk |
| :--- | :--- | :--- |
| `control_plane/auth/rbac.py` | `platform_admin: {"*"}`; `check_permission` honours `*` and `resource:*`. | One flag grants every tenant permission, present and future. |
| `control_plane/auth/dependencies.py` `resolve_auth_context` | If `users.is_platform_admin` is true, any `X-Tenant-Id` yields role `platform_admin` without a membership. | Silent cross-tenant access with no reason, expiry or audit. |
| `enforce_tenant_access` | Skips the tenant check for `is_platform_admin`. | Same bypass on member routes. |
| `post_call/review/repository.py`, `post_call/webhook/repository.py` | Skip tenant and scope checks for `auth.is_platform_admin`. | Same bypass on review and webhook data. |
| `control_plane/auth/api_keys_async.py` | Accepts any role in `RBACManager.roles()`, which includes `platform_admin`. | A tenant API key could be issued with the wildcard role. |
| `control_plane/audit_routes.py` / `core/compliance/audit/queries.py` | Cross-tenant `query_all_audit_logs` when role is `platform_admin` and no tenant is given. HTTP always supplies the caller tenant, so the branch is unreachable from `/v1/audit`. | Compatibility path; kept, not exposed. |
| `/v1/me` | Returns `is_platform_admin` straight from the flag. | Studio cannot tell staff roles or capabilities apart. |
| Studio | No internal area; `controlPlaneRequest` supports only `identity` and `tenant` scopes. | — |
| Tests asserting the wildcard | `tests/auth/test_studio_identity.py::test_durable_platform_admin_requires_explicit_tenant` (200 without membership) and `voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py::test_rbac_matrix_enforcement` (`platform_admin` may write agents). | These describe the behavior being removed; they are inverted deliberately in Task 1's RED step. |

`audit_log.tenant_id` is `NOT NULL`, so platform actions need their own audit table rather than a synthetic tenant.

## Global constraints

- Exactly two platform roles. No `*` and no `resource:*` grant anywhere in either matrix.
- Platform permissions at launch:
  - `platform_admin`: `platform_tenant:read`, `platform_staff:read`, `platform_staff:write`, `platform_audit:read`.
  - `platform_support`: `platform_tenant:read`.
  Operations health and support sessions are Phase 13K and add their permissions there.
- Tenant-scoped routes accept only a durable tenant membership (or, from 13K, an explicit support grant). A platform role never satisfies a tenant permission, and no tenant requirement is ever met with an empty or synthetic tenant ID.
- Platform routes accept only OIDC bearer tokens, reject API keys, and reject requests that carry `X-Tenant-Id` or `X-Actor-Role`.
- API-key roles are limited to tenant roles; unknown roles fail closed.
- Every staff grant, role change and revocation needs a reason and writes a platform audit event in the same transaction. The last active `platform_admin` cannot be revoked or demoted.
- Every tenant-detail read by staff writes a platform audit event. The directory is bounded (`limit` ≤ 50, `offset` ≤ 10 000) and searchable by name or exact tenant ID.
- Internal responses carry safe metadata only: no credential values, key material, token hashes, transcripts, recordings or customer contact data beyond the staff member's own email.
- `users.is_platform_admin` stays in the schema for compatibility but is no longer read for authorization; `/v1/me` derives `is_platform_admin` from the durable role so existing clients keep parsing.
- Platform tables are not granted to `ucve_app`; they are reached only through `platform_transaction`.
- Studio `/admin` uses Theme B tokens and the existing primitives; no new runtime dependency, no colour literal outside `:root`.
- No live IdP, provider, carrier, deployment, payment or publication.

## Review focus

- No remaining code path turns a platform role into tenant access (grep `is_platform_admin` and `platform_admin` after Task 1).
- Customers reaching `/admin` see a not-found page, not a hint that it exists; staff lacking a capability see a denial without data.
- Last-platform-admin protection holds under concurrent revokes (row lock in PostgreSQL).
- No secret, token or customer payload in internal responses, Studio HTML or the client bundle.

## Rollback point

The plan commit is the clean checkpoint before the multi-file backend change. Each task is one atomic commit and can be reverted on its own; Task 1 (wildcard removal) and Task 2 (migration) are independent of the Studio tasks.

---

### Task 1: Explicit platform permission registry and wildcard removal

**Files:**
- Create: `control_plane/auth/platform_rbac.py` (`PlatformRole`, `PLATFORM_PERMISSIONS`, `platform_permissions_for_role`, `check_platform_permission`)
- Modify: `control_plane/auth/rbac.py` (drop `platform_admin`; drop `*`/`resource:*` matching; `roles()` returns tenant roles only)
- Modify: `control_plane/auth/dependencies.py` (`resolve_auth_context` requires a membership; `enforce_tenant_access` has no bypass; API-key roles must be tenant roles)
- Modify: `post_call/review/repository.py`, `post_call/webhook/repository.py` (remove the platform bypass)
- Modify: `control_plane/auth/context.py` (keep `is_platform_admin` property for compatibility; documented as always false on tenant contexts)
- Modify: `tests/auth/test_studio_identity.py`, `voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py`
- Create: `tests/auth/test_platform_rbac.py`

- [ ] Step 1: failing tests — no role in either matrix holds `*` or `resource:*`; `platform_admin` and `platform_support` hold exactly the launch permissions; a tenant role never holds a `platform_*` permission; a flagged user without membership gets 403 for a tenant route; a flagged user with a `tenant_viewer` membership gets viewer permissions only; `enforce_tenant_access` rejects a mismatched tenant for every context; API-key creation rejects `platform_admin`; post-call review/webhook reject cross-tenant access for every role.
- [ ] Step 2: RED — `uv run --frozen --python 3.12 python -m pytest -q tests/auth tests/post_call voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN plus the full forced-offline Python suite.
- [ ] Step 5: commit `fix(auth): replace platform wildcard with explicit staff permissions`

### Task 2: Durable platform memberships and platform audit (migration 032)

**Files:**
- Create: `infra/db/migrations/032_platform_staff_roles.sql`
  - `platform_memberships(user_id PK → users, role CHECK IN ('platform_admin','platform_support'), granted_by → users NULL, granted_at, reason NOT NULL, revoked_at, revoked_by, revoke_reason)`; partial index on active rows.
  - `platform_audit_events(id, actor_user_id → users, action, target_user_id NULL, target_tenant_id NULL, reason NULL, metadata JSONB, created_at)`; index on `created_at DESC`.
  - Backfill: every `users.is_platform_admin = TRUE` becomes an active `platform_admin` with reason `migrated from users.is_platform_admin`, plus one audit event each. Idempotent.
  - `REVOKE ALL` on both tables from `ucve_app`; RLS enabled and forced with no `ucve_app` policy.
- Modify: `control_plane/studio/models.py` (`PlatformRole`, `PlatformMembership`, `PlatformAuditEvent`, `TenantDirectoryEntry`, `TenantSummary`)
- Modify: `control_plane/studio/repository.py` (protocol + in-memory: `get_platform_role`, `list_platform_staff`, `grant_platform_role`, `revoke_platform_role`, `list_tenant_directory`, `get_tenant_summary`, `record_platform_event`, `list_platform_audit`; `LastPlatformAdminError`, `StaffNotFoundError`)
- Modify: `control_plane/studio/pg_repository.py` (same methods in `platform_transaction`, `FOR UPDATE` on active admin rows when revoking/demoting)
- Create: `tests/auth/test_platform_repository.py` (in-memory contract)
- Create: `tests/db/test_phase13j_live_platform_roles.py` (gated by `RUN_LIVE_DB_TESTS`)

- [ ] Step 1: failing tests — grant requires a reason and an existing user; re-grant changes the role and audits it; revoke requires a reason; the last active admin cannot be revoked or demoted; revoked staff resolve to no role; directory bounds and search by name or exact ID; tenant summary returns counts and entitlements only; every staff change writes exactly one audit event. Live DB: migration applied once per checksum, backfill and idempotent re-run, CHECK rejects unknown roles, `ucve_app` cannot read either table, concurrent last-admin revoke leaves one admin.
- [ ] Step 2: RED — `pytest -q tests/auth/test_platform_repository.py`; live file with the disposable database.
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Python suite; disposable PostgreSQL run of the 13H and 13J live files.
- [ ] Step 5: commit `feat(auth): add durable platform staff roles and audit`

### Task 3: Platform authorization dependency and internal API

**Files:**
- Modify: `control_plane/auth/dependencies.py` (`PlatformContext`, `require_platform_permission`)
- Create: `control_plane/routes/platform.py`
  - `GET /v1/platform/me` — role and capabilities.
  - `GET /v1/platform/tenants?q=&limit=&offset=` — `platform_tenant:read`.
  - `GET /v1/platform/tenants/{tenant_id}` — `platform_tenant:read`, audited.
  - `GET /v1/platform/staff` — `platform_staff:read`.
  - `PUT /v1/platform/staff` (`email`, `role`, `reason`) — `platform_staff:write`.
  - `DELETE /v1/platform/staff/{user_id}` (`reason` body) — `platform_staff:write`.
  - `GET /v1/platform/audit?limit=` — `platform_audit:read`.
- Modify: `control_plane/routes/identity.py` (`/v1/me` adds `platform_role` and `platform_capabilities`; `is_platform_admin` derived from the durable role)
- Modify: `control_plane/app.py` (register router)
- Create: `tests/auth/test_platform_routes.py`

- [ ] Step 1: failing tests — every route returns 401 without a token, 401 for an API key, 400 with `X-Tenant-Id` or `X-Actor-Role`, 403 for customers and for revoked staff; support can list and view tenants but gets 403 for staff and audit; admin can do all; grant/revoke validate reason length and map last-admin to 409 and unknown user to 404; tenant detail writes an audit event; responses contain no `token_hash`, key material or credential fields; `/v1/me` reports the durable role and capabilities.
- [ ] Step 2: RED — `pytest -q tests/auth/test_platform_routes.py tests/auth/test_studio_identity.py`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Python suite; route-matrix test still passes.
- [ ] Step 5: commit `feat(control-plane): add platform staff authorization and internal api`

### Task 4: Studio platform data layer and access gate

**Files:**
- Modify: `studio/src/data/schema.ts` (`platformRoleSchema`, platform fields on `currentIdentitySchema`, tenant directory/summary, staff and audit schemas)
- Modify: `studio/src/data/control-plane.ts` (`scope: "platform"` — never sends `x-tenant-id`)
- Create: `studio/src/auth/platform-permissions.ts`, `studio/src/auth/platform.ts` (`requirePlatform(capability?)`: customers → `notFound()`, staff lacking a capability → `/admin?error=forbidden`)
- Create: `studio/src/features/admin/data.ts`, `studio/src/features/admin/actions.ts` (grant/revoke server actions with strict zod input; repeat `requirePlatform("platform_staff:write")`)
- Modify: `studio/src/proxy.ts` (protect `/admin/:path*`)
- Modify: `studio/e2e/fixtures/offline-auth-server.mjs` (platform admin and support subjects; platform routes with FastAPI status codes)
- Create: `studio/tests/platform-access.test.ts`

- [ ] Step 1: failing tests — platform scope sends no tenant header; unknown platform role or capability fails closed; customers get not-found; support lacks staff/audit; server actions reject missing reasons before calling FastAPI and map 409 to the last-admin message.
- [ ] Step 2: RED — `npm.cmd test -- platform-access.test.ts data-boundary.test.ts`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; full Studio unit suite; typecheck.
- [ ] Step 5: commit `feat(studio): add platform data layer and access gate`

### Task 5: Internal shell, overview and tenant directory

**Files:**
- Create: `studio/src/app/(admin)/layout.tsx`, `admin/page.tsx`, `admin/tenants/page.tsx`, `admin/tenants/[tenantId]/page.tsx`, with `loading.tsx`/`error.tsx`
- Create: `studio/src/features/admin/admin-navigation.tsx`, `tenant-directory.tsx`, `tenant-summary-view.tsx`
- Modify: `studio/src/app/workspaces/page.tsx` (staff see a "Wavia admin" entry; customers do not)
- Modify: `studio/src/app/globals.css`
- Create: `studio/tests/admin-area.test.tsx`, `studio/e2e/platform-admin.spec.ts`

- [ ] Step 1: failing tests — distinct internal shell labelled "Wavia admin" with capability-filtered navigation; overview shows the staff role and only reachable destinations; directory search form, bounded table, empty-by-data vs empty-by-search, pagination controls; tenant detail shows safe metadata, member counts by role, agent count and entitlements, and a notice that customer data is not shown; no customer workspace navigation inside `/admin`.
- [ ] Step 2: RED — `npm.cmd test -- admin-area.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; `npx.cmd playwright test platform-admin.spec.ts` (support and admin journeys; customer gets not-found).
- [ ] Step 5: commit `feat(studio): add internal tenant directory`

### Task 6: Staff management and platform audit

**Files:**
- Create: `studio/src/app/(admin)/admin/staff/page.tsx`, `admin/audit/page.tsx`, with `loading.tsx`/`error.tsx`
- Create: `studio/src/features/admin/staff-manager.tsx`, `platform-audit-view.tsx`
- Modify: `studio/tests/admin-area.test.tsx`, `studio/e2e/platform-admin.spec.ts`

- [ ] Step 1: failing tests — staff table with role badges and grant dates; grant uses `FormDialog` (email, role, required reason); role change and revoke use `ConfirmDialog` with a required reason and stay open on failure; last-admin 409 shown as an alert; audit table with fixed-format UTC time, action, actor and target; support sees neither route.
- [ ] Step 2: RED — `npm.cmd test -- admin-area.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; staff and audit journeys in `platform-admin.spec.ts`.
- [ ] Step 5: commit `feat(studio): add platform staff management and audit`

### Task 7: Phase 13J close gate

**Files:** `Codex Fix/evidence/phase-13j/PROGRESS.md`, `VERIFICATION.md`, `Codex Fix/EXECUTION_TRACKER.md`, `docs/design-system/project-profile.md`, `studio/e2e/phase13h-shell-qa.spec.ts` (admin routes)

- [ ] Step 1: full forced-offline Python suite, ruff, mypy on changed modules, plan integrity.
- [ ] Step 2: disposable PostgreSQL — migrations 001–032 from empty, 13H and 13J live files, then teardown with no containers, volumes or networks left.
- [ ] Step 3: Studio `npm.cmd test`, `typecheck`, `lint`, `CIRCLE_NODE_TOTAL=1 npm.cmd run build`, full `npx.cmd playwright test`.
- [ ] Step 4: scans — no `*` grant; no `is_platform_admin` read on an authorization path; no `style=` or colour literal outside `:root`; protected paths; secret signatures; client bundle; `git diff --check`.
- [ ] Step 5: visual QA — desktop and 390px captures for every admin route under gitignored `hamza_local/phase13j-qa/`.
- [ ] Step 6: evidence and tracker; label live IdP, MFA/step-up for staff, Safari, real devices and screen readers as unverified.
- [ ] Step 7: commit `test(platform): close phase 13j platform security foundation`, then stop and report before Phase 13K.
