# Phase 13H verification — customer access and shell completion

**Status:** Task 7 verified locally (focused scope below). The Task 8 close gate has **not** run; Phase 13H is not complete.

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
