# Wavia Studio dashboard redesign — pilot design brief

**Status:** revised reference direction approved; ready for pilot implementation  
**Date:** 2026-11-06  
**Pilot:** `SCR-01` Agent Directory and `SCR-03` Persona Editor only

## 1. Outcome and boundaries

Wavia Studio is the authenticated operating surface for building and running Wavia voice agents. It is not the public marketing website. This pilot will establish a professional SaaS shell and reusable primitives, then apply them only to the agent directory and persona editor. It must preserve every existing route, server action, role check, API contract, test journey and user-visible capability.

The pilot will not add billing, deploy anything, contact a live provider, place a call, redesign the public website, add marketing composition, or roll the visual system across the remaining Studio routes.

## 2. Source precedence

1. Hamzi's dashboard-redesign brief and explicit Wavia brand direction.
2. Current Studio behavior, access model and content in `studio/`, including the audited `SCR-01` through `SCR-13` inventory.
3. Proven mature SaaS console structure: persistent collapsible sidebar, contextual top bar, route-derived tabs, compact tables/forms and explicit states.
4. Compatible dashboard, form, state and accessibility guidance from `SURFACES.md`, `DESIGN.md` and `PRE-SHIP.md`.

Explicit deviation: **Wavia Studio uses the current Wavia website palette and type; the older VERTEX navy/Inter system is superseded for this surface.**

The cancelled Mobbin/Quo reference is not a dependency. Wavia Theme B is authoritative for Studio; Brand Kit v1.1, the checked-out steel-blue website theme and the older VERTEX navy/Inter system are superseded. The design comes from Wavia's real routes, states and access model rather than a generic dashboard template.

## 3. Current Studio audit

### Architecture and shell

- Next.js 16 App Router with strict TypeScript and React 19.
- No styling framework, global Studio stylesheet, font loader, icon library, motion library or theme mechanism.
- Authenticated shell is browser-default HTML: tenant name, user name, sign-out form, a flat navigation row and unbounded main content.
- Navigation is role-filtered and task-based, but has no active state, grouping, responsive behavior or collapsed mode.
- A safe global error boundary and not-found route exist.
- Current automated Chromium journeys use an offline auth/control-plane fixture and mock voice mode.

### Screen inventory and user jobs

| ID | Intended screen and user job | Current implementation reality | Pilot status |
| :--- | :--- | :--- | :--- |
| `SCR-01` | Agent Directory — find an agent, understand draft/published status, create, open or test it. | `/agents` exists. It renders slot usage, a create link, an empty message or a plain list. No search/filter, table composition, explicit loading state or route-local error state. | Pilot |
| `SCR-02` | Template Picker — start from a safe template or blank agent. | `/agents/new` exists with template/custom paths and limit/error/creating/created behavior. | Audit only |
| `SCR-03` | Persona Editor — shape name, description, languages, greeting, voice and prompt; understand save/readiness/publish state. | Functionality is consolidated at `/agents/[agentId]/build`, not `/persona`. Autosave, conflict, validation, publish, immutable version restore and view-only mode exist. | Pilot |
| `SCR-04` | Languages & Vocal Timbre — configure languages and per-language voices. | No dedicated route. A comma-separated language field and one voice ID are inside the current builder. | Audit only |
| `SCR-05` | Provider Priority Chains — inspect/edit advanced routing and fallbacks. | No dedicated per-agent route. Workspace credential configuration exists at `/settings/providers`; agent provider arrays remain behind current contracts. | Audit only |
| `SCR-06` | Tools & MCP Servers — connect tools safely. | No dedicated Studio route found. | Audit only |
| `SCR-07` | Knowledge Bases — upload, inspect ingestion, preview and activate trusted content. | Workspace `/knowledge` exists with PDF, DOCX, text, Markdown, CSV and XLSX upload, FAQs, lifecycle, preview and agent binding. | Audit only |
| `SCR-08` | Structured Extraction Builder — configure schemas and review limits. | No dedicated builder route found. Conversation intelligence results exist in operations. | Audit only |
| `SCR-09` | Telephony & DID Routing — inspect readiness and allowed carrier policy. | `/channels/telephony` exists for readiness and policy; carrier purchase/provisioning remains deliberately manual. | Audit only |
| `SCR-10` | Compliance & Governance — configure tier, consent and retention choices. | No dedicated route found in Studio. Compliance data remains part of agent contracts and backend policy. | Audit only |
| `SCR-11` | Interactive Test Sandbox — run an honest browser voice test and inspect transcript/latency. | `/agents/[agentId]/test` exists with mock/live labeling, connection/error state, transcript and latency. | Audit only |
| `SCR-12` | Human Review Queue — filter and resolve low-confidence results. | No dedicated queue route found. Pending review state appears in conversation detail. | Audit only |
| `SCR-13` | Live Monitor — inspect active sessions and audio health read-only. | No dedicated Studio route found. | Audit only |

This visual pilot does not create missing product routes. The inventory/reality differences remain product backlog items, not permission to change behavior.

## 4. Component inventory

### Existing behavioral components to preserve

- Workspace role-filtered navigation and sign-out.
- Agent directory data loader, entitlement limit and role-aware create/open/test actions.
- Agent draft editor: debounced autosave, save status, stale-write conflict recovery, error halt, readiness validation, publish gate, immutable version restore, advanced disclosure and viewer-safe mode.
- Global error and not-found surfaces.
- Existing semantic labels, live regions, alerts and tested accessible names.

### Shared visual primitives required by the pilot

- App shell, collapsible sidebar, nav group/item, contextual top bar and bounded content area.
- Screen header, page actions and compact supporting metadata.
- Button/link variants, form field, textarea, select-ready field wrapper, disclosure and sticky action bar.
- Status badge with non-color label, quota/usage line and technical-value treatment.
- Surface/panel, inline notice, validation summary and skeleton.
- Responsive data list/table that becomes a card list below 800px.
- Empty, loading and error state primitives.

No dependency will be added merely for decoration. Existing semantic elements remain the behavioral foundation.

## 5. Exact Wavia token mapping

The exact Theme B values and font roles below were approved by Hamzi on 2026-11-06. The framework is Next.js 16, so the free Google fonts load through `next/font/google`; no local font files or framework change are required.

### Light application palette

| Studio role | Wavia source token | Exact value |
| :--- | :--- | :--- |
| App canvas | `--studio-paper` | `#FFF6E5` |
| Primary surface | `--studio-surface` | `#FFFBF2` |
| Warm raised surface | `--studio-surface-raised` | `#FBEACD` |
| Warm muted surface/border family | `--studio-surface-muted` | `#F6E6C8` |
| Primary ink | `--studio-ink` | `#1C1408` |
| Marigold primary/focus | `--studio-accent` | `#B45309` |
| Dark surface, only where already present | `--studio-dark` | `#16120B` |

Functional green, amber, red and blue status tokens will be derived and contrast-checked during implementation, used only for real existing states and paired with text. Marigold remains the sole brand accent. `#16120B` is not permission to introduce a dark theme or decorative dark slabs; it is used only if an existing dark surface requires it.

### Typography roles

| Role | Family | Use |
| :--- | :--- | :--- |
| Operational UI | Instrument Sans | Navigation, controls, labels, body copy, tables and forms. |
| Product/display | Bricolage Grotesque | Wavia wordmark and major screen titles only. |
| Technical | Space Mono | IDs, logs, latency, code and technical values only. |
| Editorial | Instrument Serif | Retained as a brand family but not used in controls or data; no necessary use in this pilot. |

### Composition tokens to establish

- Application radii: controls around 10-12px, rows/panels around 16-18px, absolute ceiling 24px.
- Compact desktop density with 44px minimum targets retained on touch/mobile.
- Fluid shell with collapsible desktop sidebar and content capped near 1280px.
- Solid surfaces and crisp borders; no gradients, glass, blurred decorative shadows or nested-card clutter.
- Reduced functional transitions only, fully disabled by `prefers-reduced-motion` where appropriate.

## 6. Pilot screen design translation

### `SCR-01` Agent Directory

User priority: quickly understand what exists, what state each agent is in and what action is available.

- Persistent sidebar: Wavia wordmark, existing workspace identity at the top, role-filtered routes that exist today and the existing user/sign-out block pinned at the bottom. It collapses to a compact mode without hiding functionality.
- Contextual top bar: screen title, breadcrumb at route depth and the screen's primary action/search where applicable.
- Screen header: `Agents`, slot usage and one marigold `Create agent` action when authorized.
- Search and status filter operate on the loaded client-visible list without changing server contracts.
- Desktop: compact table/list with agent, description, publication status/version and actions.
- Mobile: stacked rows/cards with the same reading order and no horizontal table scroll.
- Status is always text plus shape/icon treatment, never color alone.
- States: ready list, empty workspace, empty-by-filter, loading skeleton and safe error/retry surface.

### `SCR-03` Persona Editor

User priority: make safe changes without losing work, understand what is incomplete and publish deliberately.

- Major title and concise autosave explanation in the page header.
- Main form grouped by meaning: identity, conversation opening, language/voice and advanced prompt.
- System prompt remains behind the existing Advanced disclosure and receives the required tenant-data isolation explanation without changing the stored contract.
- Agent workspace tabs derive their active state from the current route and preserve deep links. Only existing agent routes are linked in this pilot (`Persona` at `/build` and `Test Sandbox` at `/test`); missing dedicated SCR-04 through SCR-10 and SCR-12 through SCR-13 routes are reported as access/product gaps rather than replaced with broken or invented links.
- A sticky save bar appears while the draft is dirty/saving and keeps state visible; readiness and publish remain discoverable without duplicating backend actions.
- Version history remains a clear list with explicit restore action and immutable-history explanation.
- States: ready/editable, view-only, saving, saved, stale conflict, save error, validation issues, publish success, no versions and loading skeleton.
- Existing labels and tested control names remain stable.

## 7. Responsive and accessibility contract

- Desktop QA target: current Playwright desktop viewport; mobile QA target: 390px width; additionally check 320px overflow.
- Sidebar collapses to a deliberate mobile navigation treatment; fixed chrome never covers content.
- Tables become semantic card lists below 800px.
- Visible `:focus-visible` treatment on every interactive element; logical tab order; disclosure state announced.
- Minimum 44x44px touch target; mobile inputs at least 16px.
- Text contrast >=4.5:1 and large/UI boundary contrast >=3:1, measured against implemented tokens.
- Ready, empty, loading and error are present for every pilot list/table/panel. Empty-by-filter differs from empty-by-data.
- `prefers-reduced-motion` is honored. Filtering never replays entry motion.
- No horizontal overflow at 390px or 200% zoom.

## 8. Verification plan after implementation

1. Run Studio unit tests, typecheck, lint and production build.
2. Run existing Playwright journeys against the offline fixture only.
3. Capture fresh, non-committed screenshots in a gitignored `hamza_local` QA directory:
   - Agent Directory desktop: ready and empty/filter state.
   - Agent Directory mobile at 390px.
   - Persona Editor desktop: editable/saved state and validation state.
   - Persona Editor mobile at 390px with sticky actions visible.
4. Keyboard-tab both pilot screens and confirm focus, order and disclosure operation.
5. Run Axe, inspect contrast, test 320px/390px overflow, 200% zoom and reduced motion.
6. Verify the current theme only. A second theme is not claimed because Studio has no existing theme mechanism.
7. Grep the visual diff for hardcoded colors outside the token file, gradients, forbidden copy, raw IDs, secret-like material and accidental changes outside the pilot.

## 9. Resolved decisions and implementation gaps

- Mobbin/Quo is cancelled and must not be searched for or treated as a dependency.
- Theme B is final for the pilot; Brand Kit v1.1 and steel-blue values are superseded.
- Free Google Fonts delivery is approved; Next.js uses `next/font/google`.
- The current Studio has only two agent-scoped routes (`/build` and `/test`). The remaining requested agent tabs do not have routes to preserve, so this pilot will not invent them. This is reported as a product/navigation gap.
- The current permission model is preserved exactly. Any visual affordance that needs a permission or plan signal not present in code is skipped and reported rather than guessed.
