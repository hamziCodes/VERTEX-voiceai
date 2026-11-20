# Phase 13K progress — operations, support sessions and completion QA

**Branch:** `wavia-fixv1` (local; not pushed — Hamzi asked not to push until the program is complete)
**Plan:** `Codex Fix/phases/13k-operations-support-completion-implementation-plan.md` (`c1bde33`)
**Status:** Tasks 1–7 complete; close gate passed locally on 2026-11-12. **Phase 13 is functionally complete. Stopped for Hamzi's production review** — Phase 14 does not start automatically; deploy, live traffic and spend remain separate approvals (H14/H15).

## Approval

Hamzi asked to start Phase 13K on 2026-11-12 ("Start Phase 13K"). Nothing is pushed.

## Commits

| Task | Commit | Outcome |
| ---: | :--- | :--- |
| Plan | `c1bde33` | Audit of support, health and QA gaps; seven-task plan. |
| 1 | `92057b5` | Migration 033 `platform_support_sessions`; platform audit gains session and scope; repository start/list/end/authorize-read; new explicit permissions. |
| 2 | `6886cd2` | Support-session API with allowlisted configuration/readiness projections; admin-only operations snapshot; aggregate post-call job counts. |
| 3 | `33cb8a3` | Studio support sessions: start dialog on the tenant summary, session page with persistent read-only banner, list with end controls. |
| 4 | `8090b04` | Studio `/admin/operations`. |
| 5 | `d7bcd64` | Role matrix (7 roles), Axe WCAG 2.1 AA on every route, 320px pass, reduced motion, expired-grant API test; two defects fixed. |
| 6 | `ad8026d` | Final visual consistency pass at 1280/390/320px; six presentation defects fixed. |
| 7 | close-gate commit | Evidence, tracker, profile. |

## What support sessions guarantee

- Opened only from a tenant summary by staff with `platform_support_session:write`, with a reason (8–500 characters), optional ticket reference, one or both read scopes (`configuration`, `readiness`) and 15, 30 or 60 minutes. One active session per staff member and tenant (serialized with an advisory lock in PostgreSQL).
- **Read-only.** There is no write scope; the only mutating support routes start and end the session itself.
- Only the opener may read through it, only while active (database clock), only for granted scopes, and only while they still hold a platform role. Expired or ended → `410`; other staff or missing scope → `403`.
- Every start, read and end is an append-only platform audit event with the session ID and scope; the read event is written in the same request before data is returned.
- Projections are allowlists: agent name, description, languages, version, publish state and *counts* of provider routes, tools, MCP servers and knowledge bases; knowledge-base status counts; setup steps, entitlements and telephony readiness flags. Prompts, greetings, tool and MCP definitions, telephony numbers, credentials, transcripts and recordings are never returned (asserted against a fully populated agent).
- Platform admins can end anyone's session (`:manage`); support staff only their own.

## Operations health

Admin-only snapshot of real signals: control plane, database (trivial query and latency, or "Not configured" for in-memory), OIDC configured, post-call job counts by state (Attention on dead letters), live provider and telephony gates, active support sessions. Provider and carrier health are reported as **Not measured** because no probe exists and none may be added without H15. No environment-variable values or secrets are returned.

## Defects found and fixed

1. **Reduced motion did not stop animations.** The global rule only shortened transitions; the loading pulse kept animating. Animations now collapse too.
2. **Onboarding eyebrow failed WCAG AA contrast** (accent on the warning surface). Uses the warning ink token.
3. **Empty-state marks collapsed to a sliver on mobile** (`/test`, support sessions and every other empty state below 640px since 13H): the mark had a fixed flex basis but no width once the card switched to a column.
4. **Long values clipped in mobile table cards** (staff email, API-key prefix, audit action) and **role badges did not wrap**.
5. **Support banner end time crowded the tenant name** on mobile; separator spacing on desktop.
6. **Staff row actions stacked vertically on desktop.**
7. **In-memory session ordering tie** on Windows' coarse clock (test-visible only); insertion order breaks ties.

## Decisions

- Support sessions read through dedicated platform endpoints, never through tenant routes or a synthetic `X-Tenant-Id`, so tenant authorization stays membership-only (13J).
- Operations health is admin-only at launch; support receives no operations subset yet. A safe subset can be added as its own permission later.
- Customer-visible disclosure of support access (writing a tenant `audit_log` row when staff view a tenant) is not implemented; staff access is fully recorded in the platform audit. Recommended before production; needs Hamzi's product decision.
- `FastAPI` in this repo nests included routers, so the route-completeness test reads the generated OpenAPI paths.

## Not done here

- Safari, physical devices, manual screen-reader use, Windows forced colours, Lighthouse and Core Web Vitals on a deployed build.
- Live WorkOS sign-in, staff MFA/step-up, break-glass procedure (H14/H15).
- Live providers and Telnyx (H15).
- Ripple (`docs/DESIGN.md`) migration of the Studio, still awaiting approval.

## Next exact action

Report to Hamzi for the production review of Phase 13 as a whole. Wait for his decision before Phase 14 (operations/compliance hardening).
