# discovery_report.md

**Phase 0 deliverable** (guide Part E). Read-only audit of the repo as it stood at commit
`1fedcbd`, diffed against `qualicall_dashboard_spec.md` Sections 1–19.

## 0. Identity confirmation (Part E.1 / Part A Rule 2)

| Check | Result |
|---|---|
| Working directory | `E:\Finova-Internal\AwaazLabs-V2\Awaazlabs-Client-Dashboard` ✅ |
| Manifest name | `awaazlabs-client-dashboard` (`package.json`) ✅ |
| `git remote -v` | none — repo initialized standalone this session, per CTO decision that this becomes its own repository. No remote yet. |
| Fresh app scaffolded? | **No.** Existing Next.js app retained and rebuilt in place. |

---

## 1. Current application inventory

### Routes that exist

| Route | File | Lines | Status |
|---|---|---|---|
| `/` | `src/app/page.tsx` | 38 | link hub, not in spec |
| `/compliance` | `src/app/compliance/{page,compliance-client}.tsx` | 256 | not in spec |
| `/vob-queue` | `src/app/vob-queue/{page,vob-queue-client}.tsx` | 202 | spec §8, but content does not match |

### Routes referenced by the nav but **which do not exist** (dead links)

`/analytics/overall` · `/agents` · `/calls` · `/phone-numbers` · `/qualicall` · `/chat` ·
`/settings/members` · `/settings/ai-providers` · `/settings/api-keys` · `/settings/billing` ·
`/settings/organization`

Nine of the twelve nav entries in `DashboardShell.tsx` point at routes with no `page.tsx`.
The existing shell is effectively a mock-up, not a working navigation.

### Shared components that exist

| Component | File | Notes |
|---|---|---|
| `Button` | `components/ui/button.tsx` | 4 variants, hand-rolled |
| `Card` + Header/Title/Description/Content | `components/ui/card.tsx` | uses undefined `text-card-foreground` |
| `Badge` | `components/ui/badge.tsx` | 4 variants |
| `Table` + Header/Body/Row/Head/Cell/Caption | `components/ui/table.tsx` | **broken** — see §4 |
| `Tabs` + List/Trigger/Content | `components/ui/tabs.tsx` | hand-rolled; a11y defects |
| `cn()` | `lib/utils.ts` | naive join, **not** `tailwind-merge` |

### Theming source

`src/app/globals.css` CSS custom properties → `tailwind.config.ts` `theme.extend.colors`.
Extracted verbatim into `THEME_NOTES.md`. No design-token package, no styled-components,
no CSS-in-JS.

### Existing mock-data convention

**None.** `HardcodedOrgContext.tsx` holds one inline org object. `compliance-client.tsx`
and `vob-queue-client.tsx` each declare their own local fixtures inline, with their own
local status strings — precisely the duplicate-enum defect the guide's Rule 5 forbids.

### Charting

**None.** No charting library installed, no chart component, no SVG plotting code.

---

## 2. Navigation diff — current vs spec §3

Spec tree is authoritative. Route paths below are the ones this build establishes.

### KEEP (path survives; content rebuilt to spec)

| Nav item | Route |
|---|---|
| VOB Queue | `/vob-queue` |
| Members | `/settings/members` |
| Usage and Billing | `/settings/billing` |
| Organization and Locations | `/settings/organization` |

Note: "keep" means the **URL** is retained. All four page bodies are rebuilt; none of the
current content matches its spec section.

### REMOVE (exists now, absent from spec §3 — must be deleted)

| Nav item | Route | Why |
|---|---|---|
| Analytics | `/analytics/overall` | not in spec tree |
| Healthcare Analytics | `/analytics/overall` | duplicate of the above; same href, two nav entries |
| Agents (flat) | `/agents` | spec has five named agent tabs, no index |
| Calls | `/calls` | spec nests this under Conversations |
| Phone Numbers | `/phone-numbers` | spec calls this Settings › Lines and Numbers |
| Qualicall | `/qualicall` | spec calls this Quality › Quality and Optimization |
| Compliance | `/compliance` | spec's COMPLIANCE group contains **only** Audit Log |
| Support Chat | `/chat` | not in spec tree; Chats is a Conversations sub-view |
| AI Providers | `/settings/ai-providers` | not in spec |
| API Keys | `/settings/api-keys` | not in spec |

Ten entries removed. The `/compliance` page (256 lines) is deleted outright.

### ADD (in spec, not built)

| Group | Nav item | Route | Spec |
|---|---|---|---|
| HOME | Overview | `/` | §4 |
| OPERATIONS | Appointments | `/appointments` | §5 |
| OPERATIONS | Conversations › Calls | `/conversations/calls` | §10.1 |
| OPERATIONS | Conversations › Chats | `/conversations/chats` | §10.2 |
| OPERATIONS | Escalations | `/escalations` | §11 |
| AGENTS | Receptionist | `/agents/receptionist` | §6 |
| AGENTS | VOB Agent | `/agents/vob` | §7 |
| AGENTS | Chat Agents | `/agents/chat` | §9 |
| AGENTS | Review Taker | `/agents/review-taker` | §13.1 |
| AGENTS | Reengagement | `/agents/reengagement` | §14.1 |
| AGENTS | *(registry slot)* | `/agents/[slug]` | §2.6 |
| QUALITY | Quality and Optimization | `/quality` | §12 |
| QUALITY | Agent Knowledge | `/knowledge` | §15 |
| GROWTH | Reviews | `/reviews` | §13.2 |
| GROWTH | Campaigns | `/campaigns` | §14.2 |
| INSIGHTS | Reports and Exports | `/reports` | §16.1 |
| COMPLIANCE | Audit Log | `/audit-log` | §16.2 |
| SETTINGS | Lines and Numbers | `/settings/lines` | §16.5 |
| SETTINGS | Consent and Do-Not-Call | `/settings/consent` | §16.5 |
| SETTINGS | Notifications | `/settings/notifications` | §16.6 |

Twenty routes added. Top bar additionally requires: organization switcher, location filter,
mode badge, notifications bell, user menu — **none of which exist today** (the current top
bar is a single sidebar-collapse button).

---

## 3. Page diff — current vs the 19 spec sections

| § | Section | Built? |
|---|---|---|
| 1 | Product context / agent catalog | n/a — narrative |
| 2 | Global architecture (modes, roles, audit, location, envelope, registry) | ❌ none |
| 3 | Navigation architecture | ❌ wrong tree |
| 4 | Overview | ❌ |
| 5 | Appointments | ❌ |
| 6 | Receptionist | ❌ |
| 7 | VOB Agent | ❌ |
| 8 | VOB Queue | ⚠ route exists, content does not match spec |
| 9 | Chat Agents | ❌ |
| 10 | Conversations | ❌ |
| 11 | Escalations | ❌ |
| 12 | Quality and Optimization | ❌ |
| 13 | Review Taker + Reviews | ❌ |
| 14 | Reengagement + Campaigns | ❌ |
| 15 | Agent Knowledge | ❌ |
| 16 | Reports · Audit Log · Members · Billing · Org · Lines · Consent · Notifications | ❌ |
| 17 | Canonical status enums | ❌ status strings duplicated inline per file |
| 18 | Competitive position | n/a — narrative |
| 19 | Build priority order | n/a — process |

**Net: 0 of 17 buildable sections are complete.** One route path is reusable.

---

## 4. Defects found in existing code

Recorded here because they must be fixed before anything composes on top of them.

| # | File | Defect | Severity |
|---|---|---|---|
| D1 | `components/ui/table.tsx` | Tailwind arbitrary variants are **HTML-escaped**: `[&amp;_tr]:border-b`, `[&amp;_tr:last-child]:border-0`. These are not valid class names; table row borders never render. | high — silent visual failure |
| D2 | `components/ui/card.tsx` | applies `text-card-foreground`; `--card-foreground` is undefined in `globals.css`. | medium |
| D3 | `tailwind.config.ts` | maps `input: 'hsl(var(--input))'`; `--input` is undefined in `globals.css`. `border-input` is a no-op. | medium |
| D4 | `lib/utils.ts` | `cn()` is `classes.filter(Boolean).join(' ')`, not `tailwind-merge`. Later classes do **not** override earlier ones, so every primitive's `className` override silently loses to its base classes. | high — will break composition across 19 sections |
| D5 | `components/ui/tabs.tsx` | `aria-selected` on a `role="button"` element (invalid); no `role="tablist"`/`role="tab"`/`role="tabpanel"`; `useMemo` missing `setValue` dep. | medium — a11y |
| D6 | `app/compliance/compliance-client.tsx` | `any` at line 106. Violates CLAUDE.md ("NEVER use `any` in production code"). | medium — moot, file is deleted |
| D7 | `app/dashboard-shell/DashboardShell.tsx` | `features` logical expression recreated each render, destabilizing `useMemo` deps. | low |

D1–D5 are repaired in Foundation. D6–D7 are moot: both files are replaced.

---

## 5. Primitive gap analysis — existing vs spec §3.5 / guide F.5

| Required primitive | Needed by | Status |
|---|---|---|
| Stat card (+ delta variant, + tooltip-formula variant) | §4.1–4.5, every agent tab | **BUILD** |
| Standard agent-analytics page template (§2.6) | §6, 7, 9, 13.1, 14.1, `[slug]` | **BUILD** |
| Status distribution horizontal bar | §4.2, §7.2 | **BUILD** |
| Funnel | §13.1, §14.1, §14.2 | **BUILD** |
| Four-stage loop graphic, live counts, per-stage click-through | §12.1 | **BUILD** |
| Trend line with plotted event markers | §12.2 | **BUILD** |
| Hour-of-day / day-of-week heatmap | §6.2, §14.1 | **BUILD** |
| Slide-over detail drawer | §5.4, §8.2, §10.1, §10.2 | **BUILD** (Radix Dialog) |
| Masked-value-with-reveal, audited | §5.2, §10.1, §14.2 | **BUILD** |
| Aging / SLA badge (amber 24h, red 48h) | §8.1, §4.6, §11.2 | **BUILD** |
| Dismissible banner | §4.6, §5.6 | **BUILD** |
| Stacked bar chart, 7D/30D toggle | §4.1, §13.2 | **BUILD** |
| Grouped bar chart | §9.2 | **BUILD** |
| Donut | §6.2 | **BUILD** |
| Sparkline | §4.4 | **BUILD** |
| Line chart + target line | §4.5, §6.2, §7.2, §9.1 | **BUILD** |
| Grade distribution histogram | §12.2 | **BUILD** |
| Empty state | §5.6, every table | **BUILD** |
| Under Construction placeholder | Milestone 1 stubs | **BUILD** |
| Button | everywhere | **REUSE** |
| Card | everywhere | **REUSE** (fix D2) |
| Badge | status chips | **EXTEND** — add status-chip variants bound to §17 enums |
| Table | §5.2, §7.2, §8.1, §10.1, §11.1, §12.2, §14.2, §16.2 | **REUSE** (fix D1) |
| Tabs | §10 sub-views, 7D/30D toggles | **REUSE** (fix D5) |

**19 primitives to build, 3 to reuse, 2 to extend.** Zero of the chart primitives exist.

---

## 6. Gate

Both Phase 0 deliverables exist: this file and `THEME_NOTES.md`. Foundation may start.
