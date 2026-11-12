# Phase 13I verification — customer operational surfaces

**Status:** Close gate passed locally on 2026-11-12. Stopped before Phase 13J.

Machine: Windows 11, Node `v24.13.0`, Playwright `1.64.1` Chromium, Python 3.12.16 (uv, frozen lockfile). Flags for every run: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`, `RUN_LIVE_DB_TESTS=0`, `RUN_LIVE_REDIS_TESTS=0`. Studio e2e uses the offline auth/control-plane fixture with `WAVIA_VOICE_TEST_MODE=mock`. No live provider, carrier, IdP, deployment, publication or paid service was contacted.

## Per-task failure-first evidence

| Task | RED (before implementation) | GREEN |
| :--- | :--- | :--- |
| 1 Primitives | `operational-primitives.test.tsx` failed to resolve the new route `loading`/`error` modules | 53 focused (primitives, members, operations); full Studio 163; operations/members/shell QA Chromium 9 |
| 2 Knowledge | 6 of 11 knowledge tests failed (badges, delete confirmation, page header, no inline styles) | 11; full 166; knowledge Chromium 1 (first run timed out on the remount defect, fixed — see PROGRESS) |
| 3 Voice test | 2 of 14 failed (composed regions, page header) | 14; full 168; voice Chromium 1 with media, socket and audio-context release |
| 4 Channels | 4 of 21 failed | 21; full 172; channel/key/provider/viewer Chromium 4 |
| 5 Developer | 5 of 26 failed | 26; full 177; same 4 Chromium journeys, including no secret in URL, storage or console |
| 6 Operate | 5 of 17 failed | 17; full 182; operations Chromium 2 (viewer still denied audit) |
| 7 Navigation | 2 of 22 failed — Usage and Audit left no sidebar item current | 22 |

## Close gate

| Command (from `studio/` unless noted) | Result |
| :--- | :--- |
| `npm.cmd test -- --maxWorkers=1` | PASS — 15 files, **186 tests** (Phase 13H close: 145). |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run lint` | PASS — zero warnings |
| `CIRCLE_NODE_TOTAL=1 npm.cmd run build` | PASS — 22 static pages; re-run after the colour-token change also PASS |
| `npx.cmd playwright test` (full offline Chromium) | PASS — **24 passed** |
| `npx.cmd playwright test phase13h-shell-qa.spec.ts member-management.spec.ts` after the colour-token change | PASS — 7 passed |
| Root: `uv run --frozen --python 3.12 python -m pytest -q` | PASS — 985 passed, 15 skipped (no Python change in 13I) |
| Root: `verify_plan_integrity.py` | PASS — 36 phases, tests and trackers |

## Scans (range `252ac79..HEAD` plus working tree)

| Scan | Result |
| :--- | :--- |
| `style=` in `studio/src` | None (was 123 across four components and two pages). |
| Hex/`rgb()` colours in `.ts`/`.tsx` | None. |
| Colour literals in `globals.css` outside the `:root` token block | None. Three Phase 13G shell literals (card hairline shadow, drawer shadow, mobile scrim) were moved into `--studio-shadow-hairline`, `--studio-shadow-drawer` and `--studio-scrim` with identical values. |
| Gradients | None. |
| Protected paths (`.github/`, `.env`, key files, deploy, `docs/DESIGN.md`, `design-tokens.json`) | None changed. |
| Files outside `studio/` and `Codex Fix/` | None — no backend, migration or contract change. |
| Secret signatures in the 13I diff | None. |
| Client bundle (`studio/.next/static`) for session/cookie secrets, the pending-invitation cookie, fixture tokens, `x-tenant-id`, `PLATFORM_*_API_KEY`, `token_hash`, private keys | None found. |
| `console.*` in `studio/src` | Only inside the displayed SDK example snippet string in `web-channel-view.tsx`; it is not executed by Studio. |
| `git diff --check` | Clean. |

## Visual QA

`e2e/phase13h-shell-qa.spec.ts` now also covers `/knowledge`, `/channels/web`, `/channels/telephony`, `/developers/api-keys`, `/settings/providers`, `/conversations`, a conversation detail, `/settings/usage` and `/settings/audit`. On every run it asserts the level-1 heading, the sidebar, no horizontal overflow at 1280px and 390px, a hidden closed drawer at 390px, and no console or page errors.

Captures (gitignored, inspected) in `hamza_local/phase13i-qa/`: `phase13i-qa-<route>-{desktop,mobile-390}-20261112.png` for the nine routes above, plus `phase13i-qa-voice-sandbox-desktop-20261112.png` and `phase13i-qa-voice-sandbox-after-turn-desktop-20261112.png`. Inspection led to two fixes: telephony policy fields now top-align when only some have hints, and status badges no longer stretch across mobile table cards. Full-page captures distort the sticky sidebar; viewport captures were used for judgement.

## Not verified

Safari, physical devices, manual screen-reader use, Windows forced-colours, Lighthouse and Core Web Vitals on a deployed build, a dark theme (no theme mechanism exists), live WorkOS sign-in, live providers and live Telnyx. The native `<meter>` styling uses WebKit and Firefox pseudo-elements; only Chromium was exercised.
