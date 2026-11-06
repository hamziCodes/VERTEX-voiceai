# Phase 13G progress — Wavia Studio visual pilot

**Branch:** `wavia-fixv1-phase13g`  
**Base:** `07892ec`  
**Status:** Task 4 complete locally; offline browser QA and closeout next

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
- Redesigned SCR-01 with search across real agent fields, published/draft filtering, deterministic sorting, responsive table-to-card rows, role-aware actions and distinct empty workspace/filter states.
- Added route-level Agent Directory loading skeleton and safe retryable error state.
- Task 3 RED-to-GREEN evidence: the new directory test suite failed before the component existed, then its four focused tests and the full 93-test Studio suite passed; typecheck, lint and production build passed.
- Redesigned SCR-03 into identity, conversation, advanced prompt, readiness and version-history regions while preserving the existing action contracts.
- Added field-associated server validation, tenant prompt-isolation notice, dirty/saving sticky autosave status, view-only treatment and route-level loading/error states.
- Task 4 RED-to-GREEN evidence: sticky-save and inline-validation tests failed against the old editor, then nine focused builder tests and the full 94-test Studio suite passed; typecheck, lint and production build passed.

## Not started

- No screenshot captured.
- No live provider, call, deployment, paid critic or image-generation action occurred.

## Resolved inputs

- Mobbin/Quo reference cancelled.
- Wavia Theme B tokens approved.
- Free Google Fonts delivery approved; Studio framework confirmed as Next.js 16 and will use `next/font/google`.

## Next exact action

Start Task 5 with Playwright assertions and fresh desktop/mobile captures, then run the complete offline test/build/pre-ship gate and write the final verification report. Stop after the pilot.

## Resume prompt

> Continue Phase 13G from `Codex Fix/evidence/phase-13g/PROGRESS.md` and the approved `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md`. Implement only the shared shell, existing-route agent tabs, SCR-01 and SCR-03 using the Phase 13G plan. Preserve all behavior and tests; use offline fixtures only; store fresh Playwright captures under gitignored `hamza_local`; do not deploy, use live providers, place calls, generate images or run paid critics.
