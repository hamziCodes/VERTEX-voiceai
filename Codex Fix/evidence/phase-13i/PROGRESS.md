# Phase 13I progress — customer operational surfaces

**Branch:** `wavia-fixv1` (local; not pushed — Hamzi asked not to push until the program is complete)
**Plan:** `Codex Fix/phases/13i-customer-operational-surfaces-implementation-plan.md` (`9f37861`)
**Status:** Tasks 1–7 complete; close gate passed locally on 2026-11-12. Stopped before Phase 13J.

## Approval

Hamzi approved continuing past the Phase 13H review gate on 2026-11-12 ("continue"), and asked that nothing be pushed until everything is complete.

## Commits

| Task | Commit | Outcome |
| ---: | :--- | :--- |
| Plan | `9f37861` | Audit of the eight remaining customer routes and a seven-task plan. |
| 1 | `380eb1b` | Shared route tabs, confirm dialog, UTC formatter; loading/error states for ten routes; members uses the shared dialog. |
| 2 | `d839c55` | Knowledge workspace composed; delete confirmation; base switcher fixed. |
| 3 | `36c7a33` | Browser voice test composed (presentation only). |
| 4 | `287fcfb` | Web and telephony channels composed; inline styles removed. |
| 5 | `cf843c1` | API keys and provider credentials composed; shared form dialog; inline styles removed. |
| 6 | `0594512` | Conversations, usage and audit composed. |
| 7 | close-gate commit | QA coverage for every 13I route, Operate sidebar state, colour tokenisation, evidence. |

## Defects found and fixed

1. **Knowledge base switching showed stale data.** `KnowledgeManager` seeded state from props once, so choosing another base in the switcher kept the previous base on screen. It is now keyed on the requested base. A first attempt keyed on the selected base and remounted after creating a base (losing the chosen file); the Chromium journey caught that, and the key now follows only the URL choice.
2. **Deleting a knowledge source had no confirmation.** It now uses the shared confirm dialog, and the dialog stays open with the failure if deletion fails.
3. **Client-rendered dates could cause hydration mismatches.** The conversation list (a client component) used `toLocaleString()`, which depends on server/browser locale and timezone. All operational dates now use one fixed `en-GB`/UTC formatter with an explicit `UTC` suffix.
4. **No sidebar item was current on Usage and Audit.** Those routes belong to Operate but matched no navigation item. Operate (Conversations) is now current on `/conversations`, `/settings/usage` and `/settings/audit`; Providers stays separate.

## Decisions

- **Visual system:** Theme B tokens and the 13H primitives, as the plan states. Ripple (`docs/DESIGN.md`) still awaits an approved migration; everything in 13I uses `--studio-*` tokens so that migration is mostly a token and typography change.
- **No backend change.** Every route uses its existing loaders, actions and DTOs. `git diff 252ac79` touches only `studio/` and `Codex Fix/`.
- **Sentence-case headings and buttons** ("API keys", "Save policy", "Web voice integration"). Playwright name matching is case-insensitive substring, so the browser journeys still match; unit assertions were updated deliberately in each task's RED step.
- **Usage meters use native `<meter>`** with explicit value text and without `low/high/optimum` regions, so normal usage is not painted as a warning. The hard cap is still announced by its alert text.
- **Shared dialogs:** `ConfirmDialog` (destructive confirmations) and `FormDialog` (create/configure forms) replace four hand-rolled overlays. Both focus the right control, close on Escape unless busy, and return focus. The one-time API-key reveal deliberately does not use them: it ignores Escape and still requires the acknowledgement checkbox (covered by a test).
- **Remaining shell colour literals** from Phase 13G (two shadows and the mobile scrim) were moved into `:root` tokens with identical values, so the stylesheet defines colours only in its token block.

## Not done here (later phases)

- Multi-role journeys for every route and the final visual consistency pass belong to Phase 13K.
- Platform management (`/admin`, durable platform roles) belongs to Phase 13J.
- Member display names, a pending-invitations list and the query-string invitation-link question remain as recorded in Phase 13H.

## Next exact action

Report Phase 13I to Hamzi, then continue with Phase 13J (lean platform-management security foundation) — which starts with its own plan and touches backend authorization, migrations and RLS.
