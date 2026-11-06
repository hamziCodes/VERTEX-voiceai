# Phase 13G progress — Wavia Studio visual pilot

**Branch:** `wavia-fixv1-phase13g`  
**Base:** `07892ec`  
**Status:** revised design direction approved; implementation planning in progress

## Completed

- Created an isolated worktree at `.worktrees/phase-13g`.
- Audited the current Studio stack, shell, all `SCR-01` through `SCR-13` inventory entries and the implementation reality of their routes.
- Audited `SCR-01` Agent Directory and `SCR-03` Persona Editor behavior and existing tests in depth.
- Read the compatible dashboard, state, accessibility and pre-ship design guidance.
- Replaced the cancelled Mobbin dependency and superseded website themes with the approved Wavia Theme B values.
- Recorded the explicit Wavia-over-VERTEX brand deviation in `docs/design-system/project-profile.md`.
- Wrote `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md` with the screen audit, component inventory, token mapping, pilot composition, state contract and QA plan.

## Not started

- No Studio source or behavior changed.
- No dependencies installed.
- No screenshot captured.
- No tests/build run for this documentation-only checkpoint.
- No live provider, call, deployment, paid critic or image-generation action occurred.

## Resolved inputs

- Mobbin/Quo reference cancelled.
- Wavia Theme B tokens approved.
- Free Google Fonts delivery approved; Studio framework confirmed as Next.js 16 and will use `next/font/google`.

## Next exact action

Write and self-review the Phase 13G pilot implementation plan, commit the corrected brief/profile checkpoint, install the existing workspaces, run the offline baseline, then implement only the shared shell/primitives, route-derived agent tabs, `SCR-01` and `SCR-03` with test-first changes.

## Resume prompt

> Continue Phase 13G from `Codex Fix/evidence/phase-13g/PROGRESS.md` and the approved `docs/agent-studio/WAVIA_STUDIO_PILOT_DESIGN_BRIEF.md`. Implement only the shared shell, existing-route agent tabs, SCR-01 and SCR-03 using the Phase 13G plan. Preserve all behavior and tests; use offline fixtures only; store fresh Playwright captures under gitignored `hamza_local`; do not deploy, use live providers, place calls, generate images or run paid critics.
