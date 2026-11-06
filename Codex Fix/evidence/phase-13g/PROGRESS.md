# Phase 13G progress — Wavia Studio visual pilot

**Branch:** `wavia-fixv1-phase13g`  
**Base:** `07892ec`  
**Status:** Task 2 complete locally; Agent Directory implementation next

## Completed

- Created an isolated worktree at `.worktrees/phase-13g`.
- Audited the current Studio stack, shell, all `SCR-01` through `SCR-13` inventory entries and the implementation reality of their routes.
- Audited `SCR-01` Agent Directory and `SCR-03` Persona Editor behavior and existing tests in depth.
- Read the compatible dashboard, state, accessibility and pre-ship design guidance.
- Replaced the cancelled Mobbin dependency and superseded website themes with the approved Wavia Theme B values.
- Recorded the explicit Wavia-over-VERTEX brand deviation in `docs/design-system/project-profile.md`.
- Wrote `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md` with the screen audit, component inventory, token mapping, pilot composition, state contract and QA plan.
- Baseline passed before visual code: Studio 88 tests, typecheck, lint and production build.
- Added the Theme B token/font layer, responsive collapsible sidebar, role-filtered active navigation, workspace/account blocks and route-derived agent tabs.
- Agent tabs intentionally link only the two routes that exist (`/build` and `/test`); no missing SCR route was fabricated.
- Task 2 RED-to-GREEN evidence: focused shell/tab tests failed before implementation, then 90 Studio tests passed; typecheck, lint and production build passed. The build required network access only to fetch the four approved free Google fonts.

## Not started

- No screenshot captured.
- No live provider, call, deployment, paid critic or image-generation action occurred.

## Resolved inputs

- Mobbin/Quo reference cancelled.
- Wavia Theme B tokens approved.
- Free Google Fonts delivery approved; Studio framework confirmed as Next.js 16 and will use `next/font/google`.

## Next exact action

Start Task 3 with failing Agent Directory tests for search, existing-state filter/sort, role-aware actions and empty-by-filter behavior; then implement SCR-01 without changing its data or API contracts.

## Resume prompt

> Continue Phase 13G from `Codex Fix/evidence/phase-13g/PROGRESS.md` and the approved `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md`. Implement only the shared shell, existing-route agent tabs, SCR-01 and SCR-03 using the Phase 13G plan. Preserve all behavior and tests; use offline fixtures only; store fresh Playwright captures under gitignored `hamza_local`; do not deploy, use live providers, place calls, generate images or run paid critics.
