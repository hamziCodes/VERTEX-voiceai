# Phase 13I Customer Operational Surfaces Implementation Plan

> **For agentic workers:** execute task-by-task. Each task is failure-first: write or change the focused tests, run them and record the RED result, implement, run GREEN plus related suites, inspect the diff, then make the single task commit. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every remaining customer operational route onto the composed Studio dashboard system: knowledge, per-agent voice test, channels, API keys, provider credentials, conversations, usage and audit. No route inside the Studio shell may stay browser-default or carry inline styling, and every functional state must stay truthful.

**Architecture:** Presentation-only conversion over the existing server-only data loaders, server actions and FastAPI contracts. No backend or contract change is planned. Server actions and FastAPI keep repeating authorization; capability strings from `/v1/me` drive presentation only.

**Tech stack:** Next.js 16 App Router, React 19, strict TypeScript, plain CSS tokens in `studio/src/app/globals.css`, Vitest/Testing Library, Playwright offline fixture.

## Execution status (2026-11-12)

All seven tasks complete and the close gate passed locally (`380eb1b`, `d839c55`, `36c7a33`, `287fcfb`, `cf843c1`, `0594512`, then the close-gate commit). Evidence: `Codex Fix/evidence/phase-13i/`.

**Spec:** `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md` (Phase 13I section). **Prerequisite:** Phase 13H closed locally (`252ac79`); Hamzi approved continuing on 2026-11-12.

## Audit (2026-11-12)

| Route | Component(s) | Current state |
| :--- | :--- | :--- |
| `/knowledge` | `knowledge/page.tsx`, `knowledge-manager.tsx` (241 lines) | No classes, no page header; deleting a source has no confirmation; no route loading/error state. |
| `/agents/[agentId]/test` | `voice-test-console.tsx` (187 lines) | No classes; inline `<h1>` without the shared header; status and metrics unstyled. |
| `/channels/web`, `/channels/telephony` | two pages + `web-channel-view.tsx`, `telephony-channel-view.tsx` | 4 + 13 + 22 inline `style=` with hardcoded hex; tab nav hand-styled; readiness colour-only signal. |
| `/developers/api-keys` | `api-key-manager.tsx` (344 lines) | 48 inline `style=`, hex colours, hand-rolled modal overlays. |
| `/settings/providers` | `provider-credential-manager.tsx` (304 lines) | 36 inline `style=`, hex colours, hand-rolled modal overlays. |
| `/conversations`, `/conversations/[callId]` | list/detail views | No classes; client list uses `toLocaleString()` (server/browser locale and timezone hydration risk). |
| `/settings/usage`, `/settings/audit` | usage/audit views | No classes; usage has no visual meter; audit dates locale-dependent. |
| `OperationsNavigation` | `operations-navigation.tsx` | Unstyled link row. |

None of these routes has a route-level `loading.tsx` / `error.tsx`.

## Global constraints

- Theme B tokens and the shared Phase 13H primitives remain the visual authority for Studio. `docs/DESIGN.md` §9 (Ripple) keeps the Studio pilot untouched until a separately approved migration; 13I does not start that migration. Writing everything against `--studio-*` tokens keeps a later Ripple migration a token/typography change.
- No new runtime dependency. No colour, gradient, radius or duration literal outside the `:root` token block.
- Preserve every server action signature, DTO, data loader, `requireWorkspace(...)` capability, offline fixture contract and SDK/voice cleanup behavior.
- Preserve accessible names relied on by existing tests unless a test is deliberately updated in the same task's RED step (for example sentence-case headings).
- Every converted surface defines ready, empty, loading and error states and a read-only presentation when the write capability is absent.
- Dates use one fixed, hydration-safe formatter (explicit locale and UTC) instead of `toLocaleString()`.
- Destructive actions (revoke key, revoke credential, delete knowledge source) require an explicit confirmation dialog.
- No live provider, carrier, IdP, deployment, payment or publication. Live-capability text stays honest (readiness is not live qualification).

## Review focus

- No secret value (API key, provider secret, invitation token) is rendered after its one-time reveal is dismissed, persisted to browser storage or logged.
- Viewers keep read-only presentation on every route; write controls are absent or disabled with a reason.
- The voice console still mints nothing until **Start voice test**, and still releases socket, tracks and audio context.
- Telephony copy never implies purchase, campaigns or live readiness that the server did not report.

---

### Task 1: Shared operational primitives and route states

**Files:**
- Create: `studio/src/components/studio/route-tabs.tsx` (route-derived tab row for channels and operations)
- Create: `studio/src/components/studio/confirm-dialog.tsx` (modal with labelled title, focus on Cancel, Escape, focus return)
- Create: `studio/src/lib/format.ts` (`formatDateTime`, `formatDate`, `formatNumber`; fixed locale, UTC)
- Modify: `studio/src/features/members/member-manager.tsx` (use the shared dialog; behavior unchanged)
- Modify: `studio/src/features/operations/operations-navigation.tsx` (use route tabs; keep `Operations` label and link names)
- Create: `loading.tsx` and `error.tsx` for `/knowledge`, `/channels/web`, `/channels/telephony`, `/developers/api-keys`, `/settings/providers`, `/conversations`, `/conversations/[callId]`, `/settings/usage`, `/settings/audit`, `/agents/[agentId]/test`
- Modify: `studio/src/app/globals.css`
- Create: `studio/tests/operational-primitives.test.tsx`

- [ ] Step 1: failing tests for active-tab `aria-current`, capability-filtered operations tabs, dialog focus/Escape/focus-return, UTC-stable formatting, and that each new error boundary offers retry without claiming a change happened.
- [ ] Step 2: RED — `npm.cmd test -- operational-primitives.test.tsx member-management.test.tsx operations.test.tsx`
- [ ] Step 3: implement; members tests stay green unchanged.
- [ ] Step 4: GREEN plus `npm.cmd test`.
- [ ] Step 5: commit `feat(studio): add shared operational primitives`

### Task 2: Knowledge

**Files:** `studio/src/app/(studio)/knowledge/page.tsx`, `studio/src/features/knowledge/knowledge-manager.tsx`, `globals.css`, `studio/tests/knowledge.test.tsx`, `studio/e2e/knowledge.spec.ts`

- [ ] Step 1: failing tests — page header; knowledge-base switcher marks the selected base; source list shows status badges with text; deleting a source asks for confirmation (cancel keeps it, confirm calls the existing action); view-only notice; empty, processing and failed source states; activation blocked reason; preview empty and cited results.
- [ ] Step 2: RED — `npm.cmd test -- knowledge.test.tsx`
- [ ] Step 3: compose upload, FAQ, preview and activate/connect panels with shared fields; keep every action and file validation rule.
- [ ] Step 4: GREEN; `npm.cmd run test:e2e -- knowledge.spec.ts`
- [ ] Step 5: commit `feat(studio): compose knowledge workspace`

### Task 3: Per-agent browser voice test

**Files:** `studio/src/app/(studio)/agents/[agentId]/test/page.tsx`, `studio/src/features/voice-test/voice-test-console.tsx`, `globals.css`, `studio/tests/voice-test.test.tsx`, `studio/e2e/voice-test.spec.ts`

- [ ] Step 1: failing tests — shared page header; mode badge (Mock/Offline/Live/Live disabled) as text; connection state badge; draft-agent and view-only notices; transcript empty state; latency metrics as a definition grid with "Not measured" until reported.
- [ ] Step 2: RED — `npm.cmd test -- voice-test.test.tsx`
- [ ] Step 3: presentation only; mint, runtime, interruption and cleanup logic untouched.
- [ ] Step 4: GREEN; `npm.cmd run test:e2e -- voice-test.spec.ts` (media/socket/context release assertions must still pass).
- [ ] Step 5: commit `feat(studio): compose browser voice test`

### Task 4: Channels

**Files:** both channel pages, `web-channel-view.tsx`, `telephony-channel-view.tsx`, `globals.css`, `studio/tests/channels-credentials.test.tsx`, `studio/e2e/channels-credentials.spec.ts`

- [ ] Step 1: failing tests — shared header and route tabs; zero inline styles; web snippet keeps the SDK contract and contains no key; agent selector shows draft/published as text; telephony readiness uses badges with text; carrier/provisioning notice stays; viewer sees policy read-only with no Save; save success/failure use status/alert roles.
- [ ] Step 2: RED — `npm.cmd test -- channels-credentials.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; channel journeys in `channels-credentials.spec.ts`.
- [ ] Step 5: commit `feat(studio): compose web and telephony channels`

### Task 5: Developer surfaces — API keys and provider credentials

**Files:** `developers/api-keys/page.tsx`, `settings/providers/page.tsx`, `api-key-manager.tsx`, `provider-credential-manager.tsx`, `globals.css`, `studio/tests/channels-credentials.test.tsx`, `studio/e2e/channels-credentials.spec.ts`

- [ ] Step 1: failing tests — shared headers; zero inline styles; key list as responsive table with status badges; create dialog and one-time reveal keep mandatory acknowledgement, never write storage, and the secret is gone after **Done**; revoke uses the shared confirm dialog and stays open on failure; provider catalog grouped by stage with configured/not-configured badges; secret input stays `type=password`; viewer has no configure/revoke controls; routing-tier notice keeps its text.
- [ ] Step 2: RED — `npm.cmd test -- channels-credentials.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; key and provider journeys in `channels-credentials.spec.ts`.
- [ ] Step 5: commit `feat(studio): compose developer key and provider surfaces`

### Task 6: Operate — conversations, usage and audit

**Files:** the four operate pages, `conversation-list-view.tsx`, `conversation-detail-view.tsx`, `usage-view.tsx`, `audit-view.tsx`, `globals.css`, `studio/tests/operations.test.tsx`, `studio/e2e/operations.spec.ts`

- [ ] Step 1: failing tests — shared headers and operations tabs; conversation dates via the fixed formatter (no `toLocaleString`); filters labelled; responsive table; empty-by-data and empty-by-filter distinct; detail shows transcript turns with speaker labels, recording state and intelligence/review states as text badges; usage meters expose value and limit as text plus a hard-cap alert; audit table with fixed-format time; viewer keeps audit denied.
- [ ] Step 2: RED — `npm.cmd test -- operations.test.tsx`
- [ ] Step 3: implement.
- [ ] Step 4: GREEN; `npm.cmd run test:e2e -- operations.spec.ts`
- [ ] Step 5: commit `feat(studio): compose conversations, usage and audit`

### Task 7: Phase 13I close gate

**Files:** `Codex Fix/evidence/phase-13i/PROGRESS.md`, `VERIFICATION.md`, `Codex Fix/EXECUTION_TRACKER.md`, `docs/design-system/project-profile.md`, `studio/e2e/phase13h-shell-qa.spec.ts` (extend route list)

- [ ] Step 1: `npm.cmd test`, `typecheck`, `lint`, `CIRCLE_NODE_TOTAL=1 npm.cmd run build`, full `npx.cmd playwright test`.
- [ ] Step 2: forced-offline Python suite and plan integrity (no Python change expected; confirms nothing regressed).
- [ ] Step 3: scans — no `style=` and no colour literal in `studio/src` outside the `:root` token block; no gradients; protected paths; secret signatures; client-bundle token scan; `git diff --check`.
- [ ] Step 4: visual QA — desktop and 390px captures for every 13I route, keyboard focus, overflow, console; captures under gitignored `hamza_local/phase13i-qa/`.
- [ ] Step 5: evidence and tracker; label Safari, real-device, screen-reader, Lighthouse and live checks as unverified.
- [ ] Step 6: commit `test(studio): close phase 13i operational surfaces`, then stop and report before Phase 13J.
