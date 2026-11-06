# Phase 13G verification — Wavia Studio visual pilot

**Date:** 2026-11-07

**Branch:** `wavia-fixv1-phase13g`

**Scope:** Shared Studio shell, existing-route agent tabs, `SCR-01` Agent Directory and `SCR-03` Persona Editor only.

## Outcome

The two-screen pilot is complete and verified locally. It preserves the existing authenticated routes, role decisions, server actions, API contracts and offline journeys. No live provider, call, deployment, paid critic, image generation or remaining-screen rollout occurred.

## Design authority and exact tokens

The pilot uses Wavia Theme B instead of the superseded VERTEX navy/Inter system:

| Role | Value |
| :--- | :--- |
| Paper field | `#FFF6E5` |
| Primary surface | `#FFFBF2` |
| Raised surface | `#FBEACD` |
| Muted surface | `#F6E6C8` |
| Ink | `#1C1408` |
| Single brand accent | `#B45309` |
| Existing dark surface | `#16120B` |

Instrument Sans is the operational face, Bricolage Grotesque is limited to the wordmark and major titles, Space Mono is limited to technical values, and Instrument Serif is loaded but not used for controls or data. Fonts use `next/font/google`.

## Implemented pilot

- Persistent responsive sidebar with role-filtered navigation, route-derived active state, workspace/account context and accessible collapse control.
- Agent tabs expose only the two real destinations: Persona (`/build`) and Test sandbox (`/test`).
- Agent Directory provides real-field search, draft/published filter, deterministic sort, role-aware actions and responsive table-to-record composition.
- Persona Editor preserves autosave, publish/readiness and restore behavior while adding grouped identity/conversation/advanced regions, inline validation, isolation guidance, sticky save status and responsive readiness/history panels.
- Pilot routes include ready, empty, loading and retryable error treatment. Empty-by-data and empty-by-filter are distinct.

## Access and information-architecture gaps

- Dedicated agent routes for the audited `SCR-04` through `SCR-10`, `SCR-12` and `SCR-13` surfaces do not exist in the current Studio. The pilot did not fabricate tabs or destinations for them.
- The shell links Test to the existing agent flow because no global test-agent selector route exists.
- No new permissions or role behavior were invented; server-side authorization remains authoritative.

## Browser QA captures

All captures came from the actual running Next.js Studio using the offline fixture. They are gitignored and were inspected locally; they are not committed.

- `hamza_local/phase13g-qa/phase13g-agents-desktop-20261106.png`
- `hamza_local/phase13g-qa/phase13g-agents-mobile-390-20261106.png`
- `hamza_local/phase13g-qa/phase13g-persona-desktop-20261106.png`
- `hamza_local/phase13g-qa/phase13g-persona-mobile-390-20261106.png`

The captures confirm the paper/ink/marigold hierarchy, compact navigation, desktop table, mobile record layout, responsive form stacking and readable sticky-shell composition. The black `N` badge visible in development captures is Next.js's local development indicator, not product UI.

## Automated verification

| Gate | Result |
| :--- | :--- |
| Studio unit suite | PASS — 10 files, 94 tests |
| Chromium Playwright suite | PASS — 17 journeys |
| Pilot Axe checks | PASS — no serious or critical violations on Agent Directory or Persona Editor |
| TypeScript | PASS — `tsc --noEmit` |
| ESLint | PASS — zero warnings |
| Next.js production build | PASS — 19 static/dynamic route entries generated |
| 390px and 320px overflow assertions | PASS |
| Reduced-motion usability assertion | PASS |

The initial full browser run found the pre-existing `Operate` accessible-navigation contract had been lost when the visible item became `Conversations`. The final implementation preserves both names in one accessible label, and both operations journeys pass. Axe also caught and drove fixes for the initial active-link contrast and wordmark label mismatch.

## Pre-ship report

Surface: Wavia Studio pilot · Archetype: dashboard with form-flow region

Density: compact shell / comfortable form · Motion budget: reduced

### Blockers (A)

- Tokens: PASS for the pilot. Core colors live in `globals.css`; component rules consume variables. No gradients or second brand accent were introduced.
- Both themes: LIGHT PASS. Dark mode is not applicable to the current product because no theme mechanism exists; deviation 2 records why Phase 13G did not invent one.
- Accessibility: PASS for automated pilot scope. Axe, keyboard-first focus checks, semantic labels, `aria-current`, `aria-expanded`, status text and 44px control rules were checked. Active-nav contrast and wordmark naming defects found during QA were fixed.
- States: PASS for the pilot components. Ready, empty-by-data, empty-by-filter, loading and error states exist; autosave/publish async states retain their existing contracts.
- Motion: PASS for implemented behavior. Only shared short CSS transitions exist; Playwright verified usability with reduced motion and filters do not replay list animation.
- Content: PASS. Copy uses real product concepts and offline fixture data; no lorem ipsum, invented performance claims or banned marketing terms were added.

### Required (B)

- Dashboard archetype and compact density are declared on the shell.
- Application radii remain at or below 20px; content is capped at 1280px.
- Playwright verified no horizontal overflow at 390px and 320px; the directory becomes record cards below 800px.
- Strict TypeScript, lint and production build pass; no new runtime dependency was added.
- Wavia font/type deviation is recorded because the older Inter-only requirement is intentionally superseded.

## Not verified / release-level follow-up

- Dark theme, because the product has no theme mechanism.
- Safari on macOS/iOS, a physical Android device, screen-reader operation and Windows forced-colors mode.
- Lighthouse, 200% browser zoom, production Core Web Vitals and first-load font behavior on a deployed build.
- Full manual throttling of loading states; route loading components were statically reviewed and existing async journeys passed.
- `npm ci` reported 8 moderate dependency advisories during baseline setup. They were not auto-fixed because dependency upgrades are outside this visual pilot.

These are release-qualification items, not evidence of a failed local pilot. They remain explicit rather than being inferred as passing.

## Stop condition

Phase 13G stops here for Hamzi's review. No remaining Studio screen may be restyled, merged, pushed or deployed without the next instruction.
