# Phase 13H Customer Access and Shell Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the lean five-role customer access model and a complete, consistently composed customer Studio foundation with working Settings, Members and Test entry routes.

**Architecture:** FastAPI remains the permission authority and returns safe capability lists with each durable workspace membership. Next.js uses those capabilities only for presentation while server actions and FastAPI repeat authorization. Phase 13H extends the approved Theme B shell to foundational customer routes, adds only the three missing routes needed to repair current navigation, and defers operational-route conversion to Phase 13I.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PostgreSQL migrations, Next.js 16 App Router, React 19, strict TypeScript, plain CSS, Vitest/Testing Library and Playwright.

**Spec:** `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md`

## Execution Status (2026-11-09)

- Tasks 1-6 are complete and committed as `83e6b73`, `176dd8e`, `361f54b`, `bb8668c`, `6965b3d` and `635fa15`.
- Task 6 checkpoint verification passed: 119 Studio tests, typecheck, lint, production build and one focused offline Chromium voice journey.
- Tasks 7-8 have not started. Phase 13H is not complete until both tasks and the full close gate pass.
- The canonical continuation and decision handover is `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md`.

## Global Constraints

- Launch customer roles are exactly `tenant_admin`, `tenant_editor`, `tenant_developer`, `tenant_viewer` and `compliance_admin`.
- Platform roles are outside Phase 13H; no platform wildcard, `/admin` route or support session is implemented here.
- Backend authorization remains authoritative; browser capability checks never grant access.
- API-key machine roles remain `tenant_viewer` and `tenant_editor`; they are not changed to human `tenant_developer` roles.
- Add only `/settings`, `/settings/members` and `/test`; do not fabricate historical SCR routes without production contracts.
- Preserve current WorkOS/OIDC session handling, tenant isolation, RLS, action signatures and offline fixtures.
- No secret value in logs, screenshots, source, docs or commits.
- No payment, deploy, package publication, live provider request or live call.
- Theme B, approved fonts and the two Phase 13G pilot screens remain the visual authority.
- Final decorative polish is deferred; no route may remain browser-default after its Phase 13H conversion.

## Review Focus

- Unknown or forged roles/capabilities fail closed in FastAPI and Studio.
- The last tenant administrator cannot be demoted or removed, including through the new Members UI.
- Invitation tokens are returned once, never logged, and remain server-protected until the explicit one-time reveal.
- Sidebar collapse persists on desktop without hydration mismatch; mobile navigation remains reachable and never covers content.
- Draft agents appear in `/test` with an honest disabled reason; only published eligible agents link into the sandbox.

---

### Task 1: Add the lean developer role and backend capability truth

**Files:**
- Create: `infra/db/migrations/031_studio_customer_roles.sql`
- Modify: `control_plane/auth/rbac.py`
- Modify: `control_plane/studio/models.py`
- Modify: `control_plane/routes/identity.py`
- Modify: `control_plane/studio/repository.py`
- Modify: `control_plane/studio/pg_repository.py`
- Test: `tests/studio/test_identity_api.py`
- Test: `tests/studio/test_studio_repository.py`
- Test: `tests/auth/test_studio_identity.py`
- Test: `tests/auth/test_route_matrix.py`
- Create: `tests/db/test_phase13h_customer_roles_migration.py`

**Interfaces:**
- Produces: `StudioRole` including `tenant_developer`.
- Produces: `RBACManager.permissions_for_role(role: str) -> frozenset[str]`.
- Produces: `/v1/me.memberships[].capabilities: list[str]`, sorted deterministically.
- Defines `tenant_developer` as exactly `agent:read`, `session:mint`, `session:read`, `usage:read`, `entitlement:read`, `telephony:read`, `api_key:read`, `api_key:write` and `provider_credential:read`.
- Preserves: API-key role/scopes and all tenant-admin/editor/viewer/compliance permissions unless a failing least-privilege test proves an existing mismatch.

- [ ] **Step 1: Write failing role and migration tests**

Assert that `tenant_developer` can read agents/sessions/catalog, mint test sessions, manage eligible API keys and read provider metadata, but cannot manage members, onboarding, compliance, telephony policy or stored provider credentials. Assert unknown roles have no permissions. Assert migration constraints allow exactly the five launch membership/invitation roles.

- [ ] **Step 2: Run focused backend tests and confirm RED**

Run: `py -3.12 -m pytest tests/studio/test_identity_api.py tests/studio/test_studio_repository.py tests/auth/test_studio_identity.py tests/auth/test_route_matrix.py tests/db/test_phase13h_customer_roles_migration.py -q`

Expected: failures for the missing role, capability list and migration.

- [ ] **Step 3: Implement the role, explicit permission bundle and migration**

Migration `031` adds a validated membership-role constraint and replaces the invitation-role constraint without changing existing valid rows. `permissions_for_role` returns an immutable set and unknown roles return an empty set. `/v1/me` adds safe, sorted capabilities to each membership response.

- [ ] **Step 4: Run focused backend tests and confirm GREEN**

Run the Step 2 command; expected all pass.

- [ ] **Step 5: Commit**

Commit: `feat(auth): add lean Studio developer role`

### Task 2: Consume backend capabilities in Studio and eliminate role-matrix drift

**Files:**
- Create: `studio/src/auth/capabilities.ts`
- Modify: `studio/src/data/schema.ts`
- Modify: `studio/src/data/dto.ts`
- Modify: `studio/src/auth/workspace-permissions.ts`
- Modify: `studio/src/auth/workspace.ts`
- Modify: `studio/src/features/workspaces/workspace-navigation.tsx`
- Modify: `studio/src/features/operations/operations-navigation.tsx`
- Modify: `studio/src/app/(studio)/layout.tsx`
- Modify: `studio/e2e/fixtures/offline-auth-server.mjs`
- Test: `studio/tests/workspace-access.test.tsx`
- Test: `studio/tests/data-boundary.test.ts`

**Interfaces:**
- Produces: `WorkspaceCapability` union for known presentation capabilities.
- Produces: `hasWorkspaceCapability(capabilities: readonly string[], required: WorkspaceCapability) -> boolean`.
- Consumes: `/v1/me.memberships[].capabilities` from Task 1.
- Preserves: the role name for display and audit context; it no longer acts as Studio's independent permission truth.

- [ ] **Step 1: Write failing capability-consumption tests**

Cover all five roles, unknown capability failure, forged role text with no capability, developer navigation, viewer read-only navigation and compliance-only navigation.

- [ ] **Step 2: Run focused Studio tests and confirm RED**

Run: `npm.cmd test -- workspace-access.test.tsx data-boundary.test.ts`

Expected: failures because membership DTOs lack capabilities and navigation still uses the local role matrix.

- [ ] **Step 3: Implement safe schemas and capability-driven presentation**

Reject malformed membership responses, ignore unknown capability strings for presentation, and pass the selected membership's capabilities through layouts and navigation. Keep every server action protected by its existing backend permission.

- [ ] **Step 4: Update the offline fixture for all five role journeys**

Fixture `/v1/me` returns deterministic capability arrays matching Task 1 without exposing internal scopes or tokens.

- [ ] **Step 5: Run focused and full Studio unit suites**

Run: `npm.cmd test -- workspace-access.test.tsx data-boundary.test.ts`

Run: `npm.cmd test`

Expected: all pass.

- [ ] **Step 6: Commit**

Commit: `refactor(studio): consume server capabilities`

### Task 3: Complete the responsive, persistent customer shell

**Files:**
- Create: `studio/src/features/workspaces/sidebar-preference.ts`
- Modify: `studio/src/features/workspaces/workspace-navigation.tsx`
- Modify: `studio/src/app/globals.css`
- Modify: `studio/tests/workspace-access.test.tsx`
- Modify: `studio/e2e/studio-visual-pilot.spec.ts`

**Interfaces:**
- Produces: versioned non-sensitive local preference key `wavia:studio:sidebar:v1`.
- Produces: explicit desktop collapse/expand control and mobile drawer control.
- Preserves: role/capability filtering, active routes, keyboard order and 44px targets.

- [ ] **Step 1: Write failing shell interaction tests**

Cover saved collapse restore, invalid stored values, accessible name/state, Escape closing the mobile drawer, focus return to the mobile trigger and no content overlap at 390px/320px.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm.cmd test -- workspace-access.test.tsx`

- [ ] **Step 3: Implement collapse persistence and density adjustment**

Use a small inline SVG icon, tooltip/title and `aria-expanded`. Read local storage after mount to avoid hydration mismatch. Reduce shell/body operational text and group spacing one step while keeping form inputs at 16px on mobile and controls at least 44px.

- [ ] **Step 4: Run focused tests and pilot Playwright**

Run: `npm.cmd test -- workspace-access.test.tsx`

Run: `npm.cmd run test:e2e -- studio-visual-pilot.spec.ts`

Expected: all pass, no horizontal overflow.

- [ ] **Step 5: Commit**

Commit: `feat(studio): refine persistent dashboard shell`

### Task 4: Build shared customer primitives and complete entry/workspace surfaces

**Files:**
- Create: `studio/src/components/studio/page-header.tsx`
- Create: `studio/src/components/studio/status-badge.tsx`
- Create: `studio/src/components/studio/state-panel.tsx`
- Create: `studio/src/components/studio/form-field.tsx`
- Modify: `studio/src/app/page.tsx`
- Modify: `studio/src/app/sign-in/page.tsx`
- Modify: `studio/src/app/workspaces/page.tsx`
- Modify: `studio/src/app/error.tsx`
- Modify: `studio/src/app/not-found.tsx`
- Modify: `studio/src/app/globals.css`
- Create: `studio/tests/studio-entry.test.tsx`
- Modify: `studio/e2e/auth-workspaces.spec.ts`

**Interfaces:**
- Produces: focused primitives used by at least two Phase 13H routes; no generic component framework.
- Preserves: WorkOS sign-in, invitation handoff, workspace selection, session cookies and sign-out.

- [ ] **Step 1: Write failing entry/workspace state tests**

Cover no membership, pending invitation, multiple workspaces, forbidden/invalid selection feedback, loading/error composition and accessible primary actions.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm.cmd test -- studio-entry.test.tsx`

- [ ] **Step 3: Implement composed public and workspace-selection surfaces**

Use truthful product copy, compact branded layout and existing actions. Do not introduce marketing sections or new authentication behavior.

- [ ] **Step 4: Run focused and auth browser journeys**

Run: `npm.cmd test -- studio-entry.test.tsx`

Run: `npm.cmd run test:e2e -- auth-workspaces.spec.ts`

- [ ] **Step 5: Commit**

Commit: `feat(studio): complete secure entry surfaces`

### Task 5: Complete dashboard, onboarding and agent creation

**Files:**
- Modify: `studio/src/app/(studio)/dashboard/page.tsx`
- Modify: `studio/src/app/(studio)/onboarding/page.tsx`
- Modify: `studio/src/features/onboarding/onboarding-form.tsx`
- Modify: `studio/src/app/(studio)/agents/new/page.tsx`
- Modify: `studio/src/features/agents/agent-creation-wizard.tsx`
- Create: route-local `loading.tsx` and `error.tsx` files where absent
- Modify: `studio/src/app/globals.css`
- Modify: `studio/tests/agent-builder.test.tsx`
- Create: `studio/tests/onboarding-dashboard.test.tsx`
- Modify: `studio/e2e/agent-builder.spec.ts`

**Interfaces:**
- Dashboard consumes only real onboarding, agent, entitlement and readiness data already available through the Studio DAL.
- Agent creation preserves `createAgentAction(input)` and entitlement enforcement.
- Onboarding preserves `saveOnboardingAction(input)` and viewer read-only behavior.

- [ ] **Step 1: Write failing dashboard/onboarding/creation tests**

Cover real next actions, incomplete requirements, view-only state, template/custom selection, entitlement limit, creating/error/created states and keyboard labels.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm.cmd test -- agent-builder.test.tsx onboarding-dashboard.test.tsx`

- [ ] **Step 3: Implement the functional dashboard and composed forms**

Dashboard prioritizes the next incomplete setup action and real readiness; it does not invent metrics. Onboarding and creation use shared field/choice/action patterns and no inline styling.

- [ ] **Step 4: Run focused tests and agent-builder browser journey**

Run the Step 2 command.

Run: `npm.cmd run test:e2e -- agent-builder.spec.ts`

- [ ] **Step 5: Commit**

Commit: `feat(studio): complete guided setup surfaces`

### Task 6: Add truthful global Test entry

**Files:**
- Create: `studio/src/app/(studio)/test/page.tsx`
- Create: `studio/src/app/(studio)/test/loading.tsx`
- Create: `studio/src/app/(studio)/test/error.tsx`
- Create: `studio/src/features/voice-test/test-agent-selector.tsx`
- Modify: `studio/src/features/workspaces/workspace-navigation.tsx`
- Modify: `studio/src/app/globals.css`
- Create: `studio/tests/test-agent-selector.test.tsx`
- Modify: `studio/e2e/voice-test.spec.ts`

**Interfaces:**
- Consumes: existing `loadAgents(...)` and `agent.is_published`.
- Produces: `/test` selector linking eligible agents to `/agents/[agentId]/test`.
- Does not mint a session or contact a provider until the user explicitly starts the existing sandbox.

- [ ] **Step 1: Write failing selector tests**

Cover no agents, draft-only agents with disabled reason, published agents, viewer visibility without start permission and deterministic ordering.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm.cmd test -- test-agent-selector.test.tsx`

- [ ] **Step 3: Implement route, selector and navigation target**

The sidebar Test item points to `/test`; per-agent test behavior remains unchanged.

- [ ] **Step 4: Run focused tests and offline voice browser journey**

Run: `npm.cmd test -- test-agent-selector.test.tsx`

Run: `npm.cmd run test:e2e -- voice-test.spec.ts`

- [ ] **Step 5: Commit**

Commit: `feat(studio): add truthful test entry`

### Task 7: Add Workspace Settings and Members management

**Files:**
- Create: `studio/src/app/(studio)/settings/page.tsx`
- Create: `studio/src/app/(studio)/settings/members/page.tsx`
- Create: `studio/src/app/(studio)/settings/members/loading.tsx`
- Create: `studio/src/app/(studio)/settings/members/error.tsx`
- Create: `studio/src/features/members/types.ts`
- Create: `studio/src/features/members/data.ts`
- Create: `studio/src/features/members/actions.ts`
- Create: `studio/src/features/members/member-manager.tsx`
- Modify: `studio/src/data/schema.ts`
- Modify: `studio/src/features/workspaces/workspace-navigation.tsx`
- Modify: `studio/src/app/globals.css`
- Create: `studio/tests/member-management.test.tsx`
- Modify: `studio/e2e/fixtures/offline-auth-server.mjs`
- Create: `studio/e2e/member-management.spec.ts`

**Interfaces:**
- Consumes: existing organization member/invitation/change/remove control-plane endpoints.
- Produces: narrow server actions for invitation creation, role change and removal.
- Invitation action returns the one-time invitation URL only to the initiating admin; it is never persisted in browser storage or logs.

- [ ] **Step 1: Write failing member management tests**

Cover read-only editor list, admin invitation with exactly the five launch roles, an explicit warning when assigning `tenant_admin`, one-time reveal, role update, removal confirmation, last-admin conflict, expired/replayed invitation messaging and no token in rendered lists.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm.cmd test -- member-management.test.tsx`

- [ ] **Step 3: Implement data/actions/routes and composed management UI**

`/settings` shows only capability-eligible destinations. `/settings/members` requires `member:read`; mutation controls additionally require `member:write`.

- [ ] **Step 4: Run focused tests and member Playwright journey**

Run: `npm.cmd test -- member-management.test.tsx`

Run: `npm.cmd run test:e2e -- member-management.spec.ts`

- [ ] **Step 5: Commit**

Commit: `feat(studio): add workspace member management`

### Task 8: Phase 13H close gate

**Files:**
- Modify: `docs/design-system/project-profile.md`
- Modify: `Codex Fix/EXECUTION_TRACKER.md`
- Create: `Codex Fix/evidence/phase-13h/PROGRESS.md`
- Create: `Codex Fix/evidence/phase-13h/VERIFICATION.md`

**Interfaces:**
- Produces: verified customer-role, capability, shell and foundational-route checkpoint for Phase 13I.

- [ ] **Step 1: Run backend verification**

Run all focused Phase 13H Python tests, then the full forced-offline Python suite using the repository's established environment flags. Run Ruff, scoped mypy and compile checks for modified Python modules.

- [ ] **Step 2: Run disposable PostgreSQL verification**

Apply migrations through `031` to the disposable Phase 09 test database, verify constraints/RLS, then remove the disposable containers and volumes.

- [ ] **Step 3: Run complete Studio verification**

Run: `npm.cmd test`

Run: `npm.cmd run typecheck`

Run: `npm.cmd run lint`

Run: `npm.cmd run build`

Run: `npm.cmd run test:e2e`

- [ ] **Step 4: Run integrity and safety scans**

Run phase-plan integrity, `git diff --check`, protected-path scan, secret signature scan, client-bundle token scan, hardcoded-color/gradient scan and role/capability parity assertions.

- [ ] **Step 5: Browser visual QA**

Capture actual desktop and 390px views for workspace selection, dashboard, onboarding, creation, test selector and members. Inspect keyboard focus, overflow, mobile drawer, saved collapse preference and browser console. Store captures only under gitignored `hamza_local/phase13h-qa/`.

- [ ] **Step 6: Update tracker and verification evidence**

Record exact commands, counts, gaps and deferred Phase 13I work. Do not claim Safari, real-device, screen-reader, Lighthouse or live-provider verification unless actually run.

- [ ] **Step 7: Commit and stop**

Commit: `test(studio): close phase 13h customer foundation`

Stop for Hamzi's review. Do not begin Phase 13I, platform management, deployment or live testing without the next instruction.
