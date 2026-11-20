# Phase 13K verification — operations, support sessions and completion QA

**Status:** Close gate passed locally on 2026-11-12. Stopped for Hamzi's production review.

Machine: Windows 11, Python 3.12.16 (uv, frozen lockfile), Node `v24.13.0`, Playwright `1.64.1` Chromium, `@axe-core/playwright` 4.14.0, Docker Desktop 4.99 (engine 29.9.3). Flags: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`, `RUN_LIVE_REDIS_TESTS=0`; `RUN_LIVE_DB_TESTS=1` only for the disposable database. No live provider, carrier, identity provider, deployment, publication or paid service was contacted.

## Per-task failure-first evidence

| Task | RED | GREEN |
| :--- | :--- | :--- |
| 1 Storage | `test_support_sessions.py` failed to import `SupportSessionClosedError`; two 13J tests asserting the exact old permission sets updated deliberately. Static migration and live files written before the SQL and PostgreSQL methods but not executed RED (recorded honestly). | 5 repository + 3 static; one ordering tie fixed; disposable PostgreSQL 13H/13J/13K live 3 passed; full Python 1035 / 17 skipped |
| 2 API | 7 of 7 route tests failed (routes missing) | 7, then 8 with the expired-grant test; full Python 1042 → 1043; live operations check against PostgreSQL passed |
| 3 Studio sessions | `admin-support-sessions.test.tsx` failed to resolve the new route modules | 7; full Studio 220; support-session Chromium journey (start, duplicate refused, view, end, expiry, admin audit) |
| 4 Operations | `admin-operations.test.tsx` failed to resolve the route | 3; full Studio 223; operations Chromium journey |
| 5 Regression | 7 of 12 new Chromium tests failed: 5 from a label-reading helper bug in the test, **2 real defects** (onboarding contrast, reduced motion not stopping animations) | 12 of 12 after fixing the helper and both defects |
| 6 Visual | Review of 81 captures found 6 presentation defects (see PROGRESS) | Recaptured and re-reviewed; unit and full Chromium green |

## Close gate

| Command | Result |
| :--- | :--- |
| Root: `uv run --frozen --python 3.12 python -m pytest -q -p no:cacheprovider` | PASS — **1043 passed, 17 skipped** (13J close: 1027 / 16) |
| Root: disposable PostgreSQL `pytest tests/db` (`infra/docker/docker-compose.phase09-test.yml`, generated password) | PASS — **52 passed**; migrations 001–033 from empty; teardown 0 containers, 0 volumes, 0 networks |
| Root: `ruff check` / `ruff format --check` on the 15 changed Python files | PASS |
| Root: `mypy control_plane/auth control_plane/studio control_plane/platform control_plane/routes/platform.py post_call/jobs/repository.py` | 1 pre-existing error in `control_plane/auth/oidc_jwks.py:89` (unchanged since before 13J); none in 13K code |
| Root: `verify_plan_integrity.py` | PASS — 36 phases |
| `studio/`: `npm.cmd test -- --maxWorkers=1` | PASS — 20 files, **223 tests** (13J close: 213) |
| `studio/`: `typecheck`, `lint` | PASS — zero warnings |
| `studio/`: `CIRCLE_NODE_TOTAL=1 npm.cmd run build` | PASS — 28 static pages; 8 dynamic `/admin` routes |
| `studio/`: `npx.cmd playwright test` | PASS — **43 passed**, 6 skipped (the capture-only spec, which runs with `CAPTURE_PHASE13K=1`) (13J close: 29) |

## Regression coverage added

- **Role matrix** (`e2e/role-matrix.spec.ts`): for tenant admin, editor, developer, viewer and compliance admin, the exact sidebar items, allowed routes and every forbidden route redirecting with the forbidden message; `/admin` not found for all customers; per-workspace roles (editor is read-only in Beta); platform support and admin exact internal navigation, denials, and no customer workspace.
- **Accessibility** (`e2e/accessibility.spec.ts`): Axe `wcag2a/2aa/21a/21aa`, no serious or critical violations on all 16 customer routes, all 7 admin routes, the grant dialog, the start-session dialog and an active support session; every route free of horizontal overflow at 320px; reduced motion collapses transitions and animations.
- **Backend**: route matrix for every new platform route (unauthenticated, API key, tenant header, customer, wrong staff, expired, ended, missing scope, unknown), OpenAPI-based completeness check that every `/v1/platform/*` route rejects anonymous calls, allowlist projection test against a fully populated agent.

## Scans (range `147a1d6..HEAD`)

| Scan | Result |
| :--- | :--- |
| Wildcard grants in either matrix | None |
| Support write path | None — mutating platform routes are only staff grant/revoke (13J) and support-session start/end |
| `style=`, colour literals outside `:root`, gradients | None |
| Protected paths | None changed |
| Secret signatures | One labelled fake value `ucve_live_not-a-staff-credential` in tests |
| Client bundle (`x-tenant-id`, `token_hash`, cookie secrets, `PLATFORM_*`, invitation cookie/token, private keys, `revoke_reason`, `end_reason`, `/v1/platform/`, prompt markers) | None |
| `git diff --check` | Clean |

## Visual QA

81 captures in gitignored `hamza_local/phase13k-qa/` (`phase13k-qa-<route>-{desktop,mobile-390,mobile-320}-20261112.png` for 17 customer and 9 internal views, plus full-page support-session captures and contact sheets in `sheets/`). Reviewed at 320px for every route and desktop for every internal route; findings fixed and recaptured.

## Not verified

Safari, physical devices, manual screen-reader use, Windows forced colours (a CSS rule exists but was not exercised), Lighthouse and Core Web Vitals on a deployed build, live WorkOS sign-in, staff MFA, live providers and Telnyx, and the production database role's row-level-security bypass used by platform reads (the disposable database runs as superuser, as in earlier phases).
