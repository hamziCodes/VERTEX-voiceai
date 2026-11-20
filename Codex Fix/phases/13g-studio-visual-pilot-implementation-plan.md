# Phase 13G Wavia Studio Visual Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Wavia Theme B Studio shell, existing-route agent tabs, Agent Directory and Persona Editor visual pilot without changing product behavior or backend contracts.

**Architecture:** Keep Server Components responsible for authenticated data and actions. Add a small plain-CSS token/primitives layer, client components only for sidebar state, route-derived active navigation and directory filtering/sorting, and retain current server actions and DTOs unchanged. Route loading/error files provide honest async states without inventing data.

**Tech Stack:** Next.js 16 App Router, React 19, strict TypeScript, plain CSS, `next/font/google`, Vitest/Testing Library and Playwright.

**Spec:** `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md`

## Global Constraints

- Pilot only: shared shell, existing-route agent tabs, `SCR-01` and `SCR-03`.
- Theme B exact core tokens: `#FFF6E5`, `#FFFBF2`, `#FBEACD`, `#F6E6C8`, `#1C1408`, `#B45309`, and `#16120B` only where a dark surface already exists.
- Load Bricolage Grotesque, Instrument Sans, Space Mono and Instrument Serif through `next/font/google`; Instrument Serif is not used for controls or data.
- Preserve routes, accessible names, roles, permissions, actions, APIs and existing tests.
- No image generation, paid critic, live provider, call, deployment, new role/backend check or invented data.
- Captures are fresh files under gitignored `hamza_local` and are never committed.
- Every task ends in an atomic commit on `wavia-fixv1-phase13g`.

## Review Focus

- Viewer/editor permissions: unavailable actions remain hidden or disabled exactly as current code enforces.
- Empty-by-data and empty-by-filter: distinct copy and recovery actions.
- Mobile navigation and tables: no lost route/action and no horizontal overflow at 390px/320px.
- Autosave conflict/error: sticky status never claims saved and existing recovery remains reachable.
- Missing agent routes: tab bar never creates a broken or fake destination.

---

### Task 1: Correct design authority and checkpoint the plan

**Files:**
- Modify: `docs/design-system/project-profile.md`
- Modify: `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md`
- Modify: `Codex Fix/evidence/phase-13g/PROGRESS.md`
- Create: `Codex Fix/phases/13g-studio-visual-pilot-implementation-plan.md`

**Interfaces:**
- Produces: authoritative Theme B values, font delivery, route-gap ruling and pilot acceptance contract.

- [ ] Verify `git diff --check` and grep that Mobbin is cancelled and old palette values are not authoritative.
- [ ] Commit documentation as `docs(studio): approve phase 13g pilot direction`.

### Task 2: Establish tested Studio shell, tokens and agent tabs

**Files:**
- Create: `studio/src/app/globals.css`
- Modify: `studio/src/app/layout.tsx`
- Modify: `studio/src/app/(studio)/layout.tsx`
- Modify: `studio/src/features/workspaces/workspace-navigation.tsx`
- Create: `studio/src/features/workspaces/studio-shell.tsx`
- Create: `studio/src/features/agents/agent-workspace-tabs.tsx`
- Modify: `studio/src/app/(studio)/agents/[agentId]/build/page.tsx`
- Modify: `studio/src/app/(studio)/agents/[agentId]/test/page.tsx`
- Create or modify: `studio/tests/studio-visual-pilot.test.tsx`

**Interfaces:**
- Produces: `StudioShell`, `ScreenHeader`/shell classes and `AgentWorkspaceTabs({ agentId })`.
- Consumes: current `WorkspaceRole`, `hasWorkspacePermission`, authenticated membership/session and `signOutAction`.

- [ ] Write tests proving role-filtered navigation remains intact, active navigation derives from pathname, collapse control is accessible and tabs link only `/build` and `/test`.
- [ ] Run the focused test and verify it fails because the new shell/tabs do not exist.
- [ ] Implement Theme B tokens, Next font variables, responsive/collapsible shell and route-derived tabs.
- [ ] Run focused and full Studio unit suites; verify green.
- [ ] Commit as `feat(studio): add Wavia application shell`.

### Task 3: Build `SCR-01` Agent Directory pilot

**Files:**
- Create: `studio/src/features/agents/agent-directory.tsx`
- Modify: `studio/src/app/(studio)/agents/page.tsx`
- Create: `studio/src/app/(studio)/agents/loading.tsx`
- Create: `studio/src/app/(studio)/agents/error.tsx`
- Modify: `studio/tests/studio-visual-pilot.test.tsx`

**Interfaces:**
- Produces: `AgentDirectory({ agents, canCreate, maxAgents, canEdit })` with search, real-state filter and deterministic sort.
- Consumes: `AgentDto[]`, entitlement limit and current role decision from the server page.

- [ ] Write tests for search, published/draft filtering, deterministic name/version sorting, empty-by-filter and role-aware actions.
- [ ] Run focused test and verify expected failures.
- [ ] Implement responsive table/card list, functional status pills, row actions, empty states and route loading/error UI.
- [ ] Run focused and full Studio unit suites; verify green.
- [ ] Commit as `feat(studio): redesign agent directory pilot`.

### Task 4: Build `SCR-03` Persona Editor pilot

**Files:**
- Modify: `studio/src/features/agents/agent-draft-editor.tsx`
- Modify: `studio/src/app/(studio)/agents/[agentId]/build/page.tsx`
- Create: `studio/src/app/(studio)/agents/[agentId]/build/loading.tsx`
- Create: `studio/src/app/(studio)/agents/[agentId]/build/error.tsx`
- Modify: `studio/tests/agent-builder.test.tsx`
- Modify: `studio/tests/studio-visual-pilot.test.tsx`

**Interfaces:**
- Preserves: `AgentDraftEditor` props and all autosave/publish/restore action signatures.
- Produces: grouped form layout, field-associated validation and dirty/saving sticky status without a new save API.

- [ ] Add tests for sticky dirty/saving state, inline field validation, viewer mode, conflict/error recovery and unchanged publish/restore behavior.
- [ ] Run focused tests and verify failures are caused by missing visual/state treatment.
- [ ] Implement grouped form panels, advanced isolation notice, inline validation, sticky autosave state and responsive readiness/version regions.
- [ ] Run focused and full Studio unit suites; verify green.
- [ ] Commit as `feat(studio): redesign persona editor pilot`.

### Task 5: Offline browser QA and pilot closeout

**Files:**
- Modify: `studio/e2e/agent-builder.spec.ts`
- Create: `studio/e2e/studio-visual-pilot.spec.ts`
- Modify: `Codex Fix/evidence/phase-13g/PROGRESS.md`
- Create: `Codex Fix/evidence/phase-13g/VERIFICATION.md`
- Modify: `docs/design-system/project-profile.md`
- Modify: `Codex Fix/EXECUTION_TRACKER.md`

**Interfaces:**
- Consumes: all pilot components and offline fixture.
- Produces: desktop/mobile capture files and the final evidence report.

- [ ] Add Playwright assertions for focus, shell/tabs, directory search/filter, persona states, Axe and 390px/320px overflow.
- [ ] Run Playwright against the offline fixture and save fresh captures under `hamza_local/phase13g-qa/`.
- [ ] Run Studio unit tests, typecheck, lint, production build and full existing Chromium journeys.
- [ ] Run token/gradient/secret/protected-path/diff integrity scans and walk `PRE-SHIP.md` honestly.
- [ ] Record capture paths, results, skipped patterns, access gaps and unverified release checks.
- [ ] Commit as `test(studio): verify phase 13g visual pilot`.
- [ ] Stop. Do not style the remaining screens or merge/push without the user's next instruction.
