# Phase 13H verification — customer access and shell completion

**Status:** Phase 13H close gate passed locally on 2026-11-12 (Task 8 below). Stopped for Hamzi's review; Phase 13I has not started.

## Task 8 — Phase 13H close gate (2026-11-12)

Machine: Windows 11, Python 3.12.16 (uv, frozen lockfile), Node `v24.13.0`, Playwright `1.64.1` Chromium, Docker Desktop 4.99 / Engine 29.9.3 (installed on `D:` for this gate). Flags for every run: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`; `RUN_LIVE_DB_TESTS`/`RUN_LIVE_REDIS_TESTS=0` except inside the disposable gate. No live provider, carrier, IdP, deployment, package publication or paid service was contacted.

### Step 1 — Backend

| Command (`python -m uv run --frozen --python 3.12 …`) | Result |
| :--- | :--- |
| `python -m pytest tests/studio/test_identity_api.py tests/studio/test_studio_repository.py tests/auth/test_studio_identity.py tests/auth/test_route_matrix.py tests/db/test_phase13h_customer_roles_migration.py tests/db/test_phase13h_live_customer_roles.py -q` | PASS — 39 passed, 1 skipped (the disposable-DB test; flag off). |
| `python -m pytest tests/studio tests/auth/test_studio_identity.py tests/auth/test_route_matrix.py tests/db/test_phase13h_customer_roles_migration.py -q` (after the typing fix) | PASS — 57 passed. |
| `python -m pytest -q` (full forced-offline suite) | PASS — 985 passed, 15 skipped, 6 existing warnings. |
| `ruff check` on `control_plane/auth/rbac.py`, `control_plane/studio/models.py`, `control_plane/routes/identity.py`, `control_plane/studio/repository.py`, `control_plane/studio/pg_repository.py` and both 13H DB tests | PASS after wrapping long lines in the new DB test. |
| `mypy` (repository configuration) on the five 13H runtime modules | First run: 1 error — `identity.py:59` returned `Any` from `_repository` (a Phase 13A line, `72974c7`). Fixed with `typing.cast`, no runtime change. Re-run: **no issues in 5 source files**. A `--strict --follow-imports=skip` run was also tried; it turns pydantic/FastAPI into `Any` and reports 25 framework-typing errors, so it is not used as evidence. |
| `python -m py_compile` on the same files | PASS |

### Step 2 — Disposable PostgreSQL (migration 031)

New gated test `tests/db/test_phase13h_live_customer_roles.py` (skipped unless `RUN_LIVE_DB_TESTS=1`): migrations apply and a second run is a no-op; `031` is recorded with a checksum; `memberships_role_check` and `workspace_invitations_role_check` exist, are validated and list exactly the five launch roles; `tenant_owner`, `platform_admin` and `superadmin` are rejected on both tables (`CheckViolation`); a `tenant_developer` invitation is created and accepted through `PostgresStudioRepository`; last-admin demotion and removal raise `LastAdminError` and succeed once a second admin exists; re-running the 031 SQL over existing valid rows keeps both constraints validated; as `ucve_app` with another tenant's `app.tenant_id`, `memberships` and `workspace_invitations` rows of the first tenant are invisible (0) while the session's own tenant row is visible (1).

Recipe (as Phase 13A): a generated one-time `PHASE09_DB_PASSWORD`, `docker compose -f infra/docker/docker-compose.phase09-test.yml up -d --wait postgres` (pgvector/pg16, tmpfs data, loopback port 55432), the tests, then `docker compose … down --volumes` in a `finally` block.

| Run | Result |
| :--- | :--- |
| First attempt | Not a test result: Docker Desktop was not running after a pause, so both live tests timed out connecting. Restarted Docker Desktop. |
| `pytest tests/db/test_phase13h_live_customer_roles.py tests/db/test_phase13_live_integration.py tests/db/test_phase13h_customer_roles_migration.py tests/db/test_phase13_studio_migration.py` | PASS — 6 passed in 2.85s. |
| Same set with the Phase 13A live test first (order-independence after making the 031 check read `schema_migrations`) | PASS — 6 passed in 2.37s. |
| Cleanup after each run: `docker compose … ps -a`, compose-labelled volumes, compose-labelled networks | All empty. |

### Step 3 — Studio

| Command (in `studio/`) | Result |
| :--- | :--- |
| `npm.cmd test -- --maxWorkers=1` | PASS — 14 files, 145 tests. |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run lint` | PASS — zero warnings. |
| `CIRCLE_NODE_TOTAL=1 npm.cmd run build` | PASS — 22 static pages generated; route table includes `/settings`, `/settings/members` and `/test`. |
| `npx.cmd playwright test` (full offline Chromium suite, before the shell QA spec existed) | PASS — 21 passed. |
| `npx.cmd playwright test` (final, including the new shell QA spec) | PASS — **24 passed**. |

### Step 4 — Integrity and safety scans (Phase 13H range `c98119d..HEAD` plus the working tree)

| Scan | Result |
| :--- | :--- |
| `verify_plan_integrity.py` | PASS — `OK: 36 phases, tests, and trackers verified.` |
| `git diff --check c98119d` | Clean. |
| Protected paths | No `.github/`, `.env`, key-file or deploy change. `docs/DESIGN.md` and `docs/design/design-tokens.json` appear only through the handover commit `d18fc40` that added them; `git diff d18fc40` on both is empty. |
| Secret signatures (provider key prefixes, private keys, AWS/GitHub/Slack tokens, JWT-shaped strings) in the 13H diff | None. |
| Client bundle (`studio/.next/static`) for `WORKOS_COOKIE_PASSWORD`, `accessToken`, `refreshToken`, the test cookie password, the pending-invitation cookie name, fixture invitation tokens, `x-tenant-id`, `PLATFORM_*_API_KEY`, `token_hash`, private keys | None found. |
| Hardcoded colours / gradients | No gradients anywhere in `studio/src`; no hex after the `:root` token block in `globals.css`. Hex values remain only in the Phase 13I operational files (`channels/*`, `api-key-manager.tsx`, `provider-credential-manager.tsx`, the channel views). 13H touched only one of them (`channels/telephony/page.tsx`, Task 2), changing a permission call, not a colour. |
| Role/capability parity (script comparing `RBACManager`, the Studio `studioRoleSchema`, `WORKSPACE_CAPABILITIES`, migration 031 and the offline fixture) | PASS — 20 of 20 checks: five roles everywhere; fixture capability arrays equal FastAPI permissions for every role; Studio's capability list covers every role; unknown role → no permissions; editor reads but cannot write members; developer has no member access. |

### Step 5 — Browser visual QA

New committed spec `e2e/phase13h-shell-qa.spec.ts` asserts on every run and captures only with `CAPTURE_PHASE13H=1`:

- 1280×800 viewport: `/workspaces`, `/dashboard`, `/onboarding`, `/agents/new`, `/test`, `/settings`, `/settings/members` render their headings and the sidebar with no horizontal overflow and no console or page errors.
- 390×844: the same routes have no overflow, the closed drawer is hidden from assistive technology, the drawer opens with Settings marked current, Escape closes it and focus returns to the trigger.
- Desktop collapse persists across reload (`data-collapsed`, `aria-expanded=false`, Settings still current); the only `localStorage` key is `wavia:studio:sidebar:v1`; Tab reaches a sidebar link with a non-`none` focus outline.

Result: 3 passed. Two fixes came from running it: the test scoped its Settings locator to the sidebar (the members page also has a "← Settings" back link), and screenshots now use `caret: "initial"` because Playwright's default caret hiding injects styles before hydration and React then logs a hydration mismatch. That console error appears only while capturing, not in normal use.

Captures inspected (gitignored, `hamza_local/phase13h-qa/`): `phase13h-qa-{workspaces,dashboard,onboarding,agent-create,test-selector,settings,members}-{desktop,mobile-390}-20261112.png`, `phase13h-qa-drawer-mobile-390-20261112.png`, `phase13h-qa-members-collapsed-desktop-20261112.png`, `phase13h-qa-keyboard-focus-desktop-20261112.png`, plus the Task 7 member captures and the earlier 13H Task 4–6 captures regenerated by their specs. Inspection led to one product fix: member-row buttons no longer wrap "Update role" onto two lines at 1280px. Three captures were first taken mid-transition (drawer slide, sidebar width, streaming reload) and were retaken after the transition settled. The black "N" badge in captures is Next.js's development indicator.

### Not verified

Safari, physical mobile devices, manual screen-reader use, Windows forced-colours mode, Lighthouse and Core Web Vitals on a deployed build, a dark theme (Studio has no theme mechanism), a shared or production database migration, live WorkOS sign-in, live providers and live Telnyx. The invitee journey sets the pending-invitation cookie directly because the offline fixture does not emulate WorkOS's hosted sign-in redirect.

## Task 7 — Workspace Settings and Members (2026-11-12)

Environment flags for every command: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`. Working directory `studio/`. Windows 11, Node `v24.13.0`, npm `11.6.2`, Playwright `1.64.1` Chromium.

### Failure first (RED)

| Command | Result |
| :--- | :--- |
| `npm.cmd test -- member-management.test.tsx --maxWorkers=1` (before implementation) | FAIL as expected — `Failed to resolve import "@/app/(studio)/settings/page"`; the routes and `features/members` module did not exist. |

### GREEN

| Command | Result |
| :--- | :--- |
| `npm.cmd test -- member-management.test.tsx studio-entry.test.tsx workspace-access.test.tsx --maxWorkers=1` | First run: 44 passed, 1 failed — the pre-existing nav test used a `member:write`-only bundle that no role has; Settings now intentionally follows `member:read`. The fixture was corrected to the real admin bundle. |
| `npm.cmd test -- --maxWorkers=1` | PASS — 14 files, 145 tests (was 13 files / 119 tests at the Task 6 checkpoint). |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run lint` | PASS after removing one unused-variable warning in `member-manager.tsx` (zero warnings). |
| `npx.cmd playwright test member-management.spec.ts` (offline fixture, Chromium) | First run: 3 passed, 1 failed — a test locator matched both the product alert and Next's route announcer (the correct message was rendered). Scoped the locator; then **4 passed**. Re-run after the member-row layout fix: **4 passed**. |
| `npx.cmd playwright test member-management.spec.ts auth-workspaces.spec.ts` with `CAPTURE_PHASE13H=1` | PASS — 10 passed (4 member + 6 existing auth/workspace journeys). |
| Final `npm.cmd test -- --maxWorkers=1`, `typecheck`, `lint` after the layout fix | PASS — 145 tests; typecheck clean; zero lint warnings. |
| Baseline on the fresh machine: `uv run --frozen --python 3.12 python voice_engine_plan/scripts/verify_plan_integrity.py` | PASS — `OK: 36 phases, tests, and trackers verified.` |
| Baseline: `uv run --frozen --python 3.12 python -m pytest -q` (forced offline, `RUN_LIVE_DB_TESTS=0`, `RUN_LIVE_REDIS_TESTS=0`) | PASS — 985 passed, 14 skipped, 6 warnings (no Python code changed in Task 7). |

### Offline browser journey (`e2e/member-management.spec.ts`)

1. Administrator: Settings → Members; last-admin protection visible; tenant-admin warning; invitation reveal read from the page, token absent from local/session storage and from the member list, and absent from page HTML after **Done**; promote a member to administrator (self becomes editable); confirm removal of a member.
2. Editor: read-only list, no form or role controls; a forged `POST …/invitations` with the editor's own token is refused by the control-plane fixture (403).
3. Developer: no Settings navigation; direct `/settings/members` redirects to `/workspaces?error=forbidden`.
4. Invitee: opens the revealed link (sign-in page shows the invitation notice, token not in visible text); accepts once and lands on the dashboard; a replay shows "already been used"; the seeded expired token shows "has expired"; the administrator then sees the new member as Editor. The pending-invitation cookie is set directly in the test (mirroring `src/auth/invitation.ts`) because the offline fixture does not emulate the WorkOS hosted sign-in redirect.

Captures (gitignored, inspected): `hamza_local/phase13h-qa/phase13h-members-desktop-20261112.png`, `phase13h-members-mobile-390-20261112.png`, `phase13h-members-reveal-desktop-20261112.png`. The 390px capture asserted no horizontal overflow. Inspection led to one fix: member-row controls now sit beneath the identity so the last-admin reason no longer wraps into a narrow column. Full-page captures distort the sticky sidebar and fixed mobile trigger; Task 8 visual QA should check the shell at viewport size.

### Safety scans on the Task 7 diff

No `.github/`, `.env`, key-file, `docs/DESIGN.md` or `design-tokens.json` change; no secret signatures; no new `console.*` calls in source; no browser storage or `document.cookie` writes; no new hex/rgb colours or gradients (only existing `--studio-*` tokens); `git diff --check` clean. The dev-server-regenerated `studio/next-env.d.ts` was reverted and not committed.

### Unit coverage added (`tests/member-management.test.tsx`)

Read-only editor list; exactly five launch roles with least-privilege default; tenant-admin warning (invite and role change); one-time reveal with no `Storage.setItem` call and the token absent from the DOM after **Done**; invitation failure shows no reveal; role update; removal confirmation (cancel and confirm); last-admin UI protection; server last-admin 409 surfaced as an error; out-of-set role rejected before any upstream call; `member:write` re-checked in each action; token appears exactly once in the action result and never in `console.log/info/error`; malformed member id rejected; revalidation after removal; acceptance of expired (410), replayed (409) and wrong-email (403) invitations; transient 503 keeps the pending invitation; FastAPI's capability-less membership shape is accepted; `/settings` capability filtering and empty state; `/settings/members` requires `member:read` and hides controls without `member:write`; Settings navigation for member readers only. `tests/studio-entry.test.tsx` gained the three new invitation messages.

### Not verified in Task 7

Ruff, scoped mypy and compile checks, disposable PostgreSQL migration 031 (Docker is not installed on this machine yet), the Studio production build, the full Chromium suite, viewport-size visual QA and the full safety-scan set belong to the Task 8 close gate. No live provider, carrier, IdP, deployment or paid service was contacted.
