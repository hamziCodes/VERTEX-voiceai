# Phase 10G Verification — 2026-10-25

## Outcome

Phase 10G adds a compact, guided Knowledge Setup workspace to the local Wavia console. An operator can connect with a scoped management credential, create or select a tenant knowledge base, upload supported files, add FAQs, monitor real source states, retry or remove sources, inspect actual retrieval passages and citations, activate a complete revision, and bind it through a new immutable agent version.

Implementation commit: `ab19168` (`feat: add guided knowledge setup workspace`).

## Product and API contracts

- The management key is held only in JavaScript memory for the current tab. The visible field clears after connection. The page uses neither `localStorage` nor `sessionStorage` and contains no provider or MCP credential form.
- Base and source lists come from authenticated `/v1/knowledge-bases` APIs. Source names and API messages render through `textContent`, preventing document metadata from becoming markup.
- The new source-list route derives tenant identity from `AuthContext`, strips object references, and returns a cross-tenant 404.
- The preview endpoint validates a 1–2,000 character query and `top_k` from 1–8, derives the tenant from authentication, uses one selected base/revision, embeds locally, searches ready chunks through pgvector, and returns source ID, revision, ordinal, text, citation, and score.
- A missing local model bundle, vector mismatch, or repository failure returns a typed truthful error. The UI does not substitute sample passages.
- Uploads receive client-side type/size feedback and the existing server-side signature, MIME, archive, parser, and object-store validation. Background status remains honest.
- Activation remains unavailable until every source is ready. Binding requires an active revision and an agent UUID, then uses the existing versioned publish contract.
- Desktop uses three bounded panes so setup, current task, and source state stay visible without page scrolling. Tablet and mobile collapse to a one-column workflow with horizontally scrollable task navigation.
- Both primary console tabs and knowledge task tabs support arrow, Home, and End keys with correct `aria-selected` state. Async feedback uses polite live regions and every field keeps a visible label.

## Test-first evidence

The first focused run produced three expected frontend failures and ten API setup errors because the Knowledge Setup surface, preview dependency, and source-list endpoint did not exist. Implementation proceeded only after those missing contracts were demonstrated.

## Fresh verification

### Focused and related offline tests

- Final focused frontend/API/vector set: **20 passed**, exit 0.
- Complete frontend and RAG set: **55 passed**, exit 0.
- Coverage includes authenticated source listing, cross-tenant denial, preview bounds/citations, object-reference removal, existing ingestion/retrieval behavior, complete UI controls, non-persistence of credentials, and responsive layout contracts.

### Full forced-offline regression

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
py -3.12 -m pytest tests voice_engine_plan/tests/phase_tests -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10g-full
```

Result: **801 passed, 7 skipped, 2 warnings**, exit 0. The warnings are the existing tests that intentionally exercise short fake HMAC keys.

### Browser verification

Playwright drove installed Chrome against a local static server. API responses used generated, non-sensitive route fixtures so every connected state was deterministic and no external service was called.

- Desktop: 1440×900, three-pane workflow, zero page-level horizontal overflow, workspace 729 px within the 900 px viewport.
- Mobile: 390×844, one-column workflow, zero horizontal overflow, readable controls and source/result content.
- Arrow-key task navigation: passed.
- Real preview-result rendering and citation location: passed.
- Browser console and uncaught page errors: **0**.
- Screenshots: [`knowledge-setup-desktop.png`](knowledge-setup-desktop.png) and [`knowledge-setup-mobile.png`](knowledge-setup-mobile.png).

### Static and integrity checks

- Ruff over all changed Python source and tests: **passed**.
- Strict mypy over the new preview service: **passed**. Existing strict errors in the larger legacy repository/route modules were not claimed as new Phase 10G failures.
- JavaScript module syntax through `node --check`: **passed**.
- Python compilation and 36-phase plan integrity: **passed**.
- Diff whitespace, protected paths, and secret-pattern scan: **passed**.

## Visual critique

The desktop view keeps the current task centered while connection/progress and live source states remain visible at the sides. Status uses text plus color, and the active task has one clear primary action. The mobile view preserves the workflow order: connection, task, then source state. Long source names wrap without widening the page. The existing dark Wavia console identity is preserved without adding another visual system.

## Safety and limits

- No `.env` or raw key file was read.
- No real credential was entered, persisted, displayed, staged, or committed.
- No live STT, LLM, TTS, carrier, external MCP, cloud embedding, or business-system request occurred.
- No shared or production database was changed.
- `.github/workflows`, `legacy_codebases`, and `docs/blueprint` were untouched.
- Screenshots contain only generated browser-test data.

## Next exact action

Run Phase 10H as the final Phase 10 close: repeat the focused and complete forced-offline suites, validate disposable PostgreSQL/Redis coverage required by the phase, verify all supported format fixtures and plan integrity, scan source control for secrets/mocks/protected paths, review Phase 10 exit criteria from 10A through 10G, then mark Phase 10 complete only if every gate remains green.
