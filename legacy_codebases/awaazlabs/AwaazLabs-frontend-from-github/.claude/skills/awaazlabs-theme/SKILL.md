---
name: awaazlabs-theme
description: Use when writing ANY UI, chart, or component in the Awaazlabs-Client-Dashboard repo. Encodes the frozen design tokens, the primitive inventory, and the composition rules that the Phase 3 audit checks mechanically. Read before writing the first line of JSX.
---

# AwaazLabs Client Dashboard — theme & composition rules

The theme is **frozen**. You compose existing primitives; you do not invent styling.
Phase 3 verifies this mechanically, not by eye.

## The one rule that catches everyone

**`THEME_NOTES.md` at the repo root is the only allowed source of color.**

A hex literal, `rgb()`, `rgba()`, or raw `hsl(210 40% 96%)` anywhere in `src/` is a defect.
It will be found by:

```bash
grep -rniE "#[0-9a-f]{3,8}\b|rgb\(|rgba\(" src/
```

Use tokens. Always.

## Tokens

| Need | Use |
|---|---|
| page / card surface | `bg-background`, `bg-card` |
| primary ink | `text-foreground` |
| secondary ink, axis labels, captions | `text-muted-foreground` |
| hairline, gridline, table border | `border-border` |
| primary action | `bg-primary text-primary-foreground` |
| destructive action **and** reserved status: critical/red | `text-destructive`, `bg-destructive` |
| reserved status: amber / SLA warning | `bg-status-warning`, `text-status-warning` |
| chart series 1..6 (categorical) | `var(--chart-1)` … `var(--chart-6)` |
| heatmap magnitude (sequential) | `var(--seq-1)` … `var(--seq-5)` |

Chart tokens are **complete color values**, not HSL triples — use `var(--chart-1)` in SVG
`fill`/`stroke`, and the `chart-1` Tailwind color for `bg-`/`text-` utilities.

### Three rules about color that are not negotiable

1. **`--chart-2` (2.82:1) and `--chart-3` (2.17:1) are below 3:1 contrast.** This is legal
   *only* with a relief channel. Every chart therefore renders through `ChartFrame`, which
   requires a `series[]` legend (swatch + text label) and a `tableData` prop that it exposes
   as an `sr-only` table. Identity is never carried by color alone.
2. **Status colors are reserved.** `--destructive` and `--status-warning` mean
   critical/warning. They may never be used as "series 4". Conversely a series that *means*
   good or bad wears a status token, never a chart token. Amber is 1.83:1 by design and
   **always ships with an icon + text label**.
3. **Color follows the entity, never its rank.** Filtering a series out must not repaint the
   survivors. Bindings live once in `src/components/charts/series-map.ts` — never inline.

## Charts

- Hand-rolled SVG only. **No charting library. No new npm packages.**
- Every chart renders through `ChartFrame`.
- **One y-axis. Never a dual-axis chart.** Two measures of different scale become two charts.
- 2px line strokes; ≥8px markers; 4px rounded bar ends; 2px `hsl(var(--card))` gap between
  stacked segments; recessive horizontal-only gridlines in `hsl(var(--border))`.
- Selective direct labels — never a number on every point.
- Text wears text tokens, never the series color.
- **Funnels use a single hue** (`var(--chart-1)`) for every stage. An ordinal ramp was tested
  and rejected: the blue ladder quantizes at ΔL≈0.047, below the 0.06 floor. See
  `THEME_NOTES.md` §6. Order is carried by position, shrinking width, and stage labels.
- Responsive via `viewBox` + `preserveAspectRatio`. Never hardcode pixel widths.

## Primitives — reuse, never re-implement

Before writing a component, check whether it exists. It probably does.

`src/components/ui/` — `Button` `Card` `Badge` `Table` `Tabs` `StatusChip` `StatCard`
`Drawer` `Tooltip` `Banner` `MaskedValue` `AgingBadge` `EmptyState` `UnderConstruction`
`PageHeader` `Select`

`src/components/charts/` — `ChartFrame` `BarChart` `LineChart` `DonutChart`
`DistributionBar` `Funnel` `Heatmap` `Sparkline` `Histogram` `LoopGraphic`

Merge classes with `cn()` from `@/lib/utils` (backed by `tailwind-merge`, so later classes
correctly override earlier ones).

## Frozen files — read, import, never edit

- `src/shared/status-models.ts` — the canonical §17 enums. **Every** status chip, filter
  option, and badge imports from here. Declaring a status string literal anywhere else is a
  hard defect that Phase 3 greps for. Labels come from the `*_LABELS` maps.
- `src/shared/audit.ts` — the audit writer. Every gated action calls it.
- `src/shared/nav.ts` — the §3 nav tree, built exactly. Nothing more, nothing less.
- `src/mock/schema.ts` — data shapes. `NoPhi<T>` makes DOB/SSN/diagnosis fields
  structurally impossible; do not try to work around it.
- `src/mock/data-access.ts` — the gating layer.
- `src/mock/orgs.ts` — the two demo orgs and `MOCK_NOW_UTC`.

## Gating is structural, not cosmetic

Never hide a field with CSS or a conditional render and call it secure. The data-access
layer omits gated fields from the returned object:

- A Viewer receives `identity.phoneE164 === null`. There is nothing to reveal, so
  `MaskedValue` renders no reveal button. **Do not add your own role check** — trust the
  omission.
- A Viewer or NON-PHI session receives `media: null`. No recording URL, no transcript.
- NON-PHI mode returns `{ kind: 'aggregate', total, reason: 'NON_PHI_MODE' }` instead of
  rows. The return type is a discriminated union, so you *must* branch — you cannot
  accidentally render an empty table and call it a degraded state.

Every gated action (`revealPhone`, `playRecording`, `viewTranscript`, `recordExport`, …)
lives in `data-access.ts`, refuses first, and audits second.

## Timestamps

All fixture time derives from `MOCK_NOW_UTC` in `src/mock/orgs.ts`. **Never `Date.now()`,
never `Math.random()`** in fixtures — the seeded 48-hour-red VOB row and the "booked today"
counts must not drift with the wall clock.

Timestamps are stored UTC and rendered in the location's timezone (§2.7).

## Accessibility

Dense tables, slide-over drawers, and masked-reveal controls are this app's three biggest
a11y risks. Every interactive element: keyboard reachable, visible focus ring, correct role,
accessible name. Icon-only buttons always carry `aria-label`. Drawers trap focus and restore
it on close. Tooltips open on focus, not hover alone.

## TypeScript

`strict: true`. **No `any`, no `@ts-ignore`** — ESLint has `@typescript-eslint/no-explicit-any`
and `react/no-danger` set to `error`. Prefer the canonical union types over `string`, so an
invalid status cannot compile.

## Before you say done

```bash
npx tsc --noEmit
npm run lint
grep -rniE "#[0-9a-f]{3,8}\b|rgb\(|rgba\(" src/    # must be empty
grep -rn ": any\|as any" src/                      # must be empty
```

Then write your Part D self-audit to `progress/<section>_audit.md`: go bullet by bullet
through your assigned spec subsection, mark each ✅ / ⚠️ / ❌, and confirm no UI element
exists in your scope that cannot be traced to a spec bullet.
