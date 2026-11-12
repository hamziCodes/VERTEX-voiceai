# Phase 13H progress — customer access and shell completion

**Branch:** `wavia-fixv1`
**Plan:** `Codex Fix/phases/13h-customer-access-shell-completion-implementation-plan.md`
**Status:** Phase 13H complete locally (Tasks 1–8, close gate passed 2026-11-12). Stopped for Hamzi's review; Phase 13I not started.

## Tasks 1–6 (recorded by Codex before handover)

Commits `83e6b73`, `176dd8e`, `361f54b`, `bb8668c`, `6965b3d`, `635fa15`. Their checkpoint verification (119 Studio tests, typecheck, lint, production build, one offline Chromium voice journey) is recorded in `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md` §7 and was not re-run as part of Task 7 except where listed below.

## Task 7 — Workspace Settings and Members (Claude, 2026-11-12)

### Environment

- Fresh Windows 11 machine. Repository cloned from `hamziCodes/VERTEX-voiceai`, branch `wavia-fixv1`, base `d18fc40`.
- Node `v24.13.0` (several transitive packages warn `EBADENGINE`, wanting `^24.15.0`; install and tests still succeed). Studio dependencies installed with `npm ci` after `npm ci` in `sdk/typescript` (the Studio's `file:` SDK dependency builds with `tsc` during install).
- Playwright Chromium installed with `npx playwright install chromium`.
- Docker is not installed on this machine; nothing in Task 7 needed it.
- Safety flags for every run: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`. Studio e2e uses the offline auth/control-plane fixture and `WAVIA_VOICE_TEST_MODE=mock` from `playwright.config.ts`.

### What changed

- `/settings` lists only the settings destinations the selected membership's server capabilities allow (Members `member:read`, Usage `usage:read`, Audit `audit:read`, Provider credentials `provider_credential:read`), with an honest empty state.
- `/settings/members` requires `member:read`; invitation, role-change and removal controls render only with `member:write`. Each server action calls `requireWorkspace("member:write")` again, and FastAPI repeats `member:write`, tenant access and (for invitations) the tenant-admin check.
- Narrow server actions: `inviteMemberAction`, `changeMemberRoleAction`, `removeMemberAction`. Inputs are validated with strict Zod schemas (email, exactly the five launch roles, UUID member ids) before any upstream call.
- One-time invitation reveal: the raw token exists only inside the returned `/sign-in?invitation=…` link, held in React state until **Done**. It is never written to browser storage, never logged, and never rendered in the member list.
- Exactly five role choices (`tenant_admin`, `tenant_editor`, `tenant_developer`, `tenant_viewer`, `compliance_admin`), defaulting to the least-privileged `tenant_viewer`. Granting `tenant_admin` (invite or role change) shows an explicit warning.
- Removal requires a confirmation dialog. The last administrator's role select and Remove button are disabled with a reason, and a server 409 is surfaced as the last-administrator message rather than as success.
- Sidebar **Settings** now follows `member:read` (admins and editors) and is active only on `/settings` and `/settings/members`, so it no longer highlights on `/settings/providers`, `/settings/usage` or `/settings/audit`.
- The offline fixture now models durable members and invitations per workspace with the same status codes as `control_plane/routes/identity.py` (403/404/409/410/422) and returns FastAPI's capability-less membership shape on acceptance.

### Defects found and fixed while doing Task 7

1. **Invitation acceptance could never succeed against the real control plane.** Task 2 added `capabilities` to `workspaceSummarySchema`, but `POST /v1/invitations/accept` returns the `WorkspaceMembership` model without capabilities, so Studio would reject every successful acceptance as an invalid upstream response. The fixture had no accept route, so no test caught it. Acceptance now parses the dedicated `workspaceMemberSchema`; a unit test parses the FastAPI shape and the offline journey accepts through the fixture's FastAPI-shaped response.
2. **Expired, replayed and wrong-email invitations produced a generic error page.** Acceptance now maps 410 → `invitation-expired`, 409 → `invitation-used`, 403 → `invitation-mismatch`, 404/422 → `invalid-invitation`, deletes the pending-invitation cookie for those terminal outcomes, and keeps it for transient failures (for example 503) so the user can retry.

### Decisions (made without escalation, recorded here)

- **Visual system:** Task 7 uses the existing Theme B tokens and the shared Phase 13H primitives. `docs/DESIGN.md` §9 says the Studio pilot stays untouched until a deliberate Ripple migration, and the handover says no visual migration is authorized by itself. No new colour values were introduced; all new rules use existing `--studio-*` tokens.
- **Member identity display:** `GET /v1/organizations/{tenant}/members` returns only `user_id`, role, workspace and join date — no email or name. Rather than widen the backend contract inside a Studio task, members are shown as "You" or "Member <first 8 of id>" with the full id in a technical label, and the page states that names/emails are not shared yet. Follow-up: add a safe member display field (and a pending-invitations list) to the control-plane contract in a later phase.
- **Pending invitations are not listed** because no list-invitations endpoint exists. The only place an invitation is shown is the one-time reveal.
- **Invitation link format is unchanged** (`/sign-in?invitation=<token>`), because that is the existing Phase 13B acceptance path. Residual risk: a query-string token can appear in access logs of a proxy or host in front of Studio. Studio itself does not log it. Worth revisiting (for example a fragment-based hand-off) with the H14 hosting decision.

### Verification

Recorded in the Task 7 section of `VERIFICATION.md`.

## Task 8 — Phase 13H close gate (Claude, 2026-11-12)

- Installed Docker Desktop 4.99 on `D:` (program `D:\Docker\DockerDesktop`, data `D:\Docker\wsl`) at Hamzi's request, so the disposable PostgreSQL gate could run. The installer's temporary folder had to point at `D:` because `C:` has under 2 GB free.
- Added `tests/db/test_phase13h_live_customer_roles.py`: the first disposable-DB proof for migration 031 (validated role constraints, non-launch roles rejected, developer invite/accept, last-admin protection, idempotent re-run, cross-tenant RLS).
- Added `studio/e2e/phase13h-shell-qa.spec.ts`: a permanent regression check for the foundation routes at desktop and 390px, the mobile drawer, collapse persistence, keyboard focus and console errors.
- Fixed one pre-existing typing issue in `control_plane/routes/identity.py` (`cast` in `_repository`; no runtime change) so the repository mypy configuration passes on all 13H modules.
- Visual polish from capture review: member-row button labels stay on one line.
- Updated `docs/design-system/project-profile.md` adoption status and recorded that the Ripple references govern future work but are not yet migrated.
- Full commands and results: `VERIFICATION.md`.

## Deferred to later phases (recorded, not started)

- Phase 13I: convert the operational routes (knowledge, channels, API keys, providers, conversations, usage, audit), which still use inline styles and hardcoded colours.
- Control-plane contract: a safe member display field (name/email) and a pending-invitations list, so Members can stop showing account IDs.
- H14: decide whether the query-string invitation link needs a fragment-based hand-off for the chosen hosting setup.
- A deliberate, approved Theme B → Ripple migration task, if Hamzi wants it.

## Next exact action

STOP for Hamzi's review of Phase 13H. Do not start Phase 13I, platform management, deployment or live testing without the next instruction.
