# Charts primitive library — audit

Twelve files under `src/components/charts/`. Hand-rolled SVG only; no charting library, no new
npm packages. Color comes exclusively from THEME_NOTES.md tokens.

## File → spec subsection map

| File | Serves | Notes |
|---|---|---|
| `scales.ts` | (infrastructure) | Pure functions: `linearScale`, `bandScale`, `niceTicks`, `buildLinePath`, `buildAreaPath`, `arcPath`, `roundedRectPath`. No JSX, no DOM, unit-testable. |
| `series-map.ts` | §4.1, §5.2, §9.1, §9.2, §13.2, §5.2/§6.2 triage, §7.2/§7.3 VOB | Frozen entity→color lookups; color follows the entity in fixed slot order, never cycled. |
| `chart-frame.tsx` | THEME_NOTES §3 relief rule | Mandatory wrapper. Requires non-empty `series[]` + `tableData`. Renders legend (swatch+label+value), the chart, an always-present `sr-only` table, and a "View as table" toggle. Also exports shared `YAxis`, `SvgTooltip`, `useChartTooltip`. |
| `bar-chart.tsx` | §4.1 (stacked), §9.2 (grouped), §13.2 (stacked), §4.5 calls/minutes over time | `variant: 'stacked' \| 'grouped'`, vertical bars, 4px rounded tops, 2px `--card` gaps, one y-axis. |
| `line-chart.tsx` | §4.5, §9.1 (800ms target), §12.2 (event markers), §7.2, §13.2 | Crosshair tooltip; dashed `4 4` target line; `--foreground` ring markers on `--card` for §12.2 optimization events (hoverable via crosshair). |
| `donut-chart.tsx` | §6.2 triage donut, intake-method donut | Centre total, per-slice % direct labels outside the ring, `arcPath`. |
| `distribution-bar.tsx` | §4.2 compact VOB, §7.2 VOB distribution | Horizontal 100% stacked; integer percentages reconciled to sum to exactly 100 (largest-remainder). |
| `funnel.tsx` | §13.1 (8 stages), §14.1 (6 stages), §14.2 | SINGLE HUE `--chart-1` for every stage; per-stage count + stage-to-stage conversion % direct labels. |
| `heatmap.tsx` | §6.2 bookings-by-hour, §14.1 best-contact-window | Sequential `--seq-1`..`--seq-5` bucketed; every cell carries its numeric value as a direct label; optional `columnGroups` for business/after-hours split. |
| `sparkline.tsx` | §4.4 30-day quality sparkline | Inline, `role="img"` + required `ariaLabel`. Server-safe (no `'use client'`). See exception note below. |
| `histogram.tsx` | §12.2 grade distribution | SINGLE HUE `--chart-1`; selective count label per bar. |
| `loop-graphic.tsx` | §12.1 centerpiece | Four click-through stages with directional return arc (a loop); `--chart-1` flow, `--border` chrome; keyboard-operable nodes. |

## Confirmations

- **No literal colors.** `grep -rniE "#[0-9a-f]{3,8}\b|rgb\(|rgba\(|hsl\([0-9]" src/components/charts/` → NONE. All fills/strokes are `var(--chart-*)`, `var(--seq-*)`, `var(--status-warning)`, or `hsl(var(--border|muted-foreground|foreground|card|background|accent|muted))`.
- **No new dependencies.** Only React, `@/lib/utils` (`cn`), `@/shared/status-models`, and the existing `@/components/ui/button`.
- **ChartFrame enforces legend + table.** Its props make `series[]` and `tableData` required; it always emits an `sr-only` table (the relief channel for the sub-3:1 `--chart-2`/`--chart-3`) plus the "View as table" toggle. Every chart except the sparkline renders through it.
- **Funnel is single-hue.** `FUNNEL_HUE = 'var(--chart-1)'` for all stages; no ordinal ramp (THEME_NOTES §6).
- **No `any`.** No `: any` / `as any` / `<any>` in the directory.
- **One y-axis everywhere.** No dual-axis chart exists.

## Interpretations chosen (narrowest reasonable)

1. **Triage series colors** — triage is an ordinal severity ("means good/bad"), so per THEME_NOTES
   §3 it takes status tokens, not categorical chart tokens: None→`--border`, Low→`--muted-foreground`,
   High→`--status-warning`, Urgent→`--destructive`. Matches the spec's "red accents on High and Urgent".
2. **VOB status groups** — the eight terminal statuses collapse to three groups (verified / pending /
   needs_attention). `needs_attention`→`--destructive` (spec's red accent, §4.2); `verified`→`--chart-4`
   green (the theme has no reserved success token, so green impersonates nothing); `pending`→`--chart-1`.
3. **Four chat metrics** treated as a categorical comparison (four distinct measures), so chart tokens
   in fixed spec order — escalation is a legitimate safety outcome, not painted as a failure.
4. **Sparkline is the one ChartFrame exception** (CLAUDE.md Rule 7, conflict surfaced): a "tiny inline
   `role='img'` trend" and a full framed figure cannot both be true of one inline glyph. The more
   specific sparkline instruction wins, and it is safe because its single series uses `--chart-1`
   (4.42:1, above 3:1) — the relief obligation that makes ChartFrame mandatory does not bind.

## Verification output (actual)

```
$ npx tsc --noEmit  # (errors only in unrelated, mid-rewrite app files)
$ ... | grep "src/components/charts/"   → NO ERRORS IN src/components/charts/

$ grep -rniE "#[0-9a-f]{3,8}\b|rgb\(|rgba\(|hsl\([0-9]" src/components/charts/   → NONE (clean)

$ grep -rnE ":\s*any\b|as any|<any>|any\[\]" src/components/charts/   → NO TYPE-LEVEL any (clean)
```
