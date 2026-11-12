# Phase 13J verification — platform management security foundation

**Status:** Close gate passed locally on 2026-11-12. Stopped before Phase 13K.

Machine: Windows 11, Python 3.12.16 (uv, frozen lockfile), Node `v24.13.0`, Playwright `1.64.1` Chromium, Docker Desktop 4.99 (engine 29.9.3). Flags for every run: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`, `RUN_LIVE_REDIS_TESTS=0`; `RUN_LIVE_DB_TESTS=1` only for the disposable database run. No live provider, carrier, identity provider, deployment, publication or paid service was contacted.

## Per-task failure-first evidence

| Task | RED (before implementation) | GREEN |
| :--- | :--- | :--- |
| 1 Wildcard removal | `test_platform_rbac.py` failed to import `control_plane.auth.platform_rbac`; 4 failed in existing files (3 identity tests, 1 phase-13 plan test) | 29 focused; full Python 997 passed / 15 skipped; auth + post-call + plan tests 390 |
| 2 Migration 032 + repository | `test_platform_repository.py` failed to import `LastPlatformAdminError`. The static migration test was written after the SQL and the live file before the PostgreSQL methods; neither was run RED (recorded honestly) | 11 in-memory/static; disposable PostgreSQL 13H + 13J live 2 passed; full Python 1008 / 16 skipped |
| 3 Platform API | all 19 route tests errored in setup (`/v1/platform/staff` missing) | 46 focused, then full Python 1027 / 16 skipped |
| 4 Studio data layer | `platform-access.test.ts` failed to resolve `@/auth/platform` | 32 focused (with data-boundary); full Studio 197 |
| 5 Admin shell + directory | `admin-area.test.tsx` failed to resolve `@/app/(admin)/admin/page` | 8; full Studio 205 after updating `studio-entry` mocks with the new identity fields; Chromium 10 (platform-admin, shell QA, members) |
| 6 Staff + audit | `admin-staff-audit.test.tsx` failed to resolve `@/app/(admin)/admin/audit/page`; the support staff/audit denial journey was moved here from Task 5, where it failed because the routes did not exist | 8; full Studio 213; platform-admin Chromium 4 |

Two mistakes in my own new tests were corrected during GREEN and are not product defects: a repeated same-role grant is a deliberate no-op (one audit event, not two), and a fake token named `unknown-token` was accepted by the test provider.

## Close gate

| Command | Result |
| :--- | :--- |
| Root: `uv run --frozen --python 3.12 python -m pytest -q -p no:cacheprovider` | PASS — **1027 passed, 16 skipped** (13I close: 985 / 15) |
| Root: disposable PostgreSQL (`infra/docker/docker-compose.phase09-test.yml`, generated password, `RUN_LIVE_DB_TESTS=1`) `pytest tests/db` | PASS — **48 passed**; migrations 001–032 from empty, checksums recorded, idempotent re-run; teardown left 0 containers, 0 volumes, 0 networks |
| Root: `ruff check` on the 20 changed Python files | PASS for 13J code. Remaining findings are pre-existing in `voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py` (unused/redefined `os`, long lines, `N806`; same at `a049602`) |
| Root: `ruff format --check` | PASS except the same pre-existing plan test file (unformatted at `a049602`) |
| Root: `mypy control_plane/auth control_plane/studio control_plane/routes/platform.py control_plane/routes/identity.py post_call/review/repository.py post_call/webhook/repository.py` | 1 error, pre-existing in `control_plane/auth/oidc_jwks.py:89` (identical at `a049602`); none in 13J code |
| Root: `verify_plan_integrity.py` | PASS — 36 phases, tests and trackers |
| `studio/`: `npm.cmd test -- --maxWorkers=1` | PASS — 18 files, **213 tests** (13I close: 186) |
| `studio/`: `npm.cmd run typecheck`, `npm.cmd run lint` | PASS — zero warnings |
| `studio/`: `CIRCLE_NODE_TOTAL=1 npm.cmd run build` | PASS — 26 static pages; `/admin`, `/admin/tenants`, `/admin/tenants/[tenantId]`, `/admin/staff`, `/admin/audit` dynamic |
| `studio/`: `npx.cmd playwright test` (full offline Chromium) | PASS — **29 passed** (13I close: 24) |

## Disposable PostgreSQL proof (`tests/db/test_phase13j_live_platform_roles.py`)

- Migration 032 recorded in `schema_migrations` with a checksum; a second migration run is a no-op.
- Backfill: a user flagged `is_platform_admin` becomes an active `platform_admin` with exactly one `platform_staff.migrated` event, even after running 032 twice more.
- Grant, role change and revocation require a reason and an active platform-admin actor; unknown users return `StaffNotFoundError`; support staff cannot grant.
- The last active platform administrator cannot be revoked; two administrators revoking each other **concurrently** leave exactly one.
- Directory search and tenant summary read across tenants with real member and agent counts; the summary writes a `platform_tenant.viewed` event; a customer cannot view a summary.
- `CHECK` constraints reject unknown roles and short reasons; `UPDATE` and `DELETE` on `platform_audit_events` raise; `SET LOCAL ROLE ucve_app` cannot read either platform table.

## Scans (range `a049602..HEAD` plus working tree)

| Scan | Result |
| :--- | :--- |
| `"*"` / `resource:*` grants in `rbac.py` and `platform_rbac.py` | None |
| Reads of `.is_platform_admin` outside tests | Only comments and the identity SELECT that populates the compatibility field; no authorization decision |
| `"platform_admin"` outside tests | Platform matrix and repositories; `AuthContext.is_platform_admin` (compatibility, never true on tenant contexts); `audit_routes.py` / `core/compliance/audit/queries.py` cross-tenant branch — unreachable from HTTP because `/v1/audit` always passes the caller's tenant and tenant contexts never carry a platform role |
| `style=` in `studio/src`, colour literals outside `:root`, gradients | None |
| Protected paths (`.github/`, `.env`, key files, deploy, `docs/DESIGN.md`, `design-tokens.json`) | None changed |
| Secret signatures in added lines | One `ucve_live_` match: the labelled fake value `ucve_live_not-a-staff-credential` in `tests/auth/test_platform_routes.py` |
| Client bundle (`studio/.next/static`) for `x-tenant-id`, `token_hash`, cookie secrets, `PLATFORM_*`, pending-invitation cookie, fixture tokens, private keys, `revoke_reason`, `/v1/platform/` | None found |
| `git diff --check` | Clean |

## Visual QA

`e2e/phase13h-shell-qa.spec.ts` now also walks `/admin`, `/admin/tenants`, a tenant summary, `/admin/staff` and `/admin/audit` at 1280px and 390px, asserting the level-1 heading, the "Wavia admin" navigation (visible on desktop, hidden closed drawer on mobile), no "Workspace" navigation, no horizontal overflow, the drawer's Escape/focus return, the grant dialog's Escape/focus return and no console errors.

Captures (gitignored, inspected) in `hamza_local/phase13j-qa/`: `phase13j-qa-{overview,tenants,tenant-detail,staff,audit}-{desktop,mobile-390}-20261112.png`, `phase13j-qa-drawer-mobile-390-20261112.png`, `phase13j-qa-grant-dialog-desktop-20261112.png`. Four defects found in review were fixed and recaptured (see PROGRESS).

## Not verified

Live WorkOS sign-in for staff, MFA/step-up, Safari, physical devices, manual screen-reader use, Windows forced-colours, Lighthouse and Core Web Vitals on a deployed build, and the production database role's actual `BYPASSRLS`/ownership configuration (the disposable database runs as its superuser, as earlier phases did). Platform reads depend on that role exactly as the existing cross-tenant identity resolution already does.
