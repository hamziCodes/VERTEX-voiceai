# THEME_NOTES.md

**Phase 0 deliverable.** Verbatim design tokens for `Awaazlabs-Client-Dashboard`.

This file is the **single allowed source of color** in the codebase. The guide's Part A
Rule 3 freezes the theme; Phase 3 (Part H step 5) verifies mechanically that no color,
font, spacing unit, radius, or shadow exists outside this file. A literal hex or `hsl()`
anywhere in `src/` that is not traceable to a token below is a defect.

Theme source of truth: `src/app/globals.css` (CSS custom properties) surfaced through
`tailwind.config.ts`. Convention: base UI tokens are stored as bare HSL triples and
consumed as `hsl(var(--token))`. Chart tokens are stored as complete color values and
consumed as `var(--token)`, because SVG `fill`/`stroke` take a color, not a triple.

> ### ⚠ The two token forms are not interchangeable — this bites silently
>
> | Token family | Stored as | Use as |
> |---|---|---|
> | `--background` `--foreground` `--border` `--muted-foreground` `--primary` `--destructive` `--card` `--ring` … | HSL triple (`0 84.2% 60.2%`) | **`hsl(var(--destructive))`** |
> | `--chart-1..6` `--seq-1..5` `--status-warning` | complete color (`#ef4444`) | **`var(--chart-1)`** |
>
> Writing `fill="var(--destructive)"` resolves to the literal string `0 84.2% 60.2%`, which
> is not a valid color. SVG does not error — it silently paints the mark **black**.
> This shipped once, in the §4.2/§7.2 VOB status distribution bar, and was caught only by
> screenshotting the rendered page. `tsc`, ESLint, and the no-literal-color grep all passed.
>
> A guard exists: the Phase 3 check enumerates every HSL-triple token in `globals.css` and
> asserts each occurrence in `src/` is wrapped in `hsl()`. Re-run it after touching colors.

---

## 1. Pre-existing UI tokens (unchanged, verbatim)

Copied exactly from the scaffold at commit `1fedcbd`. Not one value altered.

| Token | Value (HSL triple) | Hex | Role |
|---|---|---|---|
| `--background` | `0 0% 100%` | `#ffffff` | page plane |
| `--foreground` | `222.2 84% 4.9%` | `#020817` | primary ink |
| `--muted` | `210 40% 96.1%` | `#f1f5f9` | recessive surface |
| `--muted-foreground` | `215.4 16.3% 46.9%` | `#64748b` | secondary ink, axis labels |
| `--border` | `214.3 31.8% 91.4%` | `#e2e8f0` | hairline, gridline |
| `--ring` | `222.2 84% 4.9%` | `#020817` | focus ring |
| `--primary` | `222.2 47.4% 11.2%` | `#0f172a` | primary action |
| `--primary-foreground` | `210 40% 98%` | `#f8fafc` | ink on primary |
| `--secondary` | `210 40% 96.1%` | `#f1f5f9` | secondary action |
| `--secondary-foreground` | `222.2 47.4% 11.2%` | `#0f172a` | ink on secondary |
| `--destructive` | `0 84.2% 60.2%` | `#ef4444` | destructive action **and** reserved status: critical |
| `--destructive-foreground` | `210 40% 98%` | `#f8fafc` | ink on destructive |
| `--accent` | `210 40% 96.1%` | `#f1f5f9` | hover wash |
| `--accent-foreground` | `222.2 47.4% 11.2%` | `#0f172a` | ink on accent |
| `--card` | `0 0% 100%` | `#ffffff` | chart surface, card surface |
| `--popover` | `0 0% 100%` | `#ffffff` | popover surface |

**Chart surface is `#ffffff`.** Every contrast figure in this file is measured against it.

### Radii, spacing, type — unchanged

| Property | Value |
|---|---|
| `borderRadius.sm` | `0.375rem` |
| `borderRadius.md` | `0.5rem` |
| `borderRadius.lg` | `0.75rem` |
| Spacing scale | Tailwind 3.4 default (`0.25rem` base unit) |
| Breakpoints | Tailwind 3.4 default (`sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1536`) |
| Shadow | `shadow-sm` only (from `Card`) |
| Typeface | browser default sans via Tailwind preflight; no webfont is loaded |

---

## 2. Repaired tokens (bug fixes, not design changes)

Three tokens were **referenced by existing code but never defined**, so they silently
resolved to nothing. Restoring them changes no intended design — it makes the existing
design actually render. Approved as bug fixes, logged in `BUILD_NOTES.md` § A1.

| Token | Value | Why it was broken |
|---|---|---|
| `--input` | `214.3 31.8% 91.4%` | `tailwind.config.ts` mapped `input: hsl(var(--input))`; the variable was never declared, so `border-input` produced no border. |
| `--card-foreground` | `222.2 84% 4.9%` | `card.tsx` applies `text-card-foreground`; undefined, so card text fell back to inherited ink by luck. |
| `--popover-foreground` | `222.2 84% 4.9%` | Same class of bug, for popover surfaces. |

Values are the shadcn/ui defaults for this exact slate palette — i.e. what the original
author demonstrably intended, matching the sibling tokens already present.

---

## 3. NEW: categorical chart palette (6 slots)

**Approved by CTO** as the only new color family in this build. Required because the spec
mandates multi-series charts (§4.1 bookings stacked by Voice/WhatsApp/Web Chat, §9.2 a
four-series grouped bar, §13.2 attributed-vs-organic stacks, §6.2 four-segment triage
donut) and the frozen theme contains exactly three usable hues.

Hues and slot order are taken **verbatim** from the `dataviz` skill's validated reference
instance (`references/palette.md`), which derived the order by maximizing minimum adjacent
CVD ΔE. **Red is deliberately excluded** from the categorical slots: this dashboard uses
red as reserved status (§4.2 needs-attention accent, §8.1 48-hour aging), and a
categorical red would impersonate it.

| Token | Hex | Hue | Contrast vs `#ffffff` |
|---|---|---|---|
| `--chart-1` | `#2a78d6` | blue | 4.42:1 |
| `--chart-2` | `#1baf7a` | aqua | 2.82:1 ⚠ |
| `--chart-3` | `#eda100` | yellow | 2.17:1 ⚠ |
| `--chart-4` | `#008300` | green | 4.95:1 |
| `--chart-5` | `#4a3aa7` | violet | 8.56:1 |
| `--chart-6` | `#eb6834` | orange | 3.20:1 |

### Validation (computed, not eyeballed)

```
node scripts/validate_palette.js "#2a78d6,#1baf7a,#eda100,#008300,#4a3aa7,#eb6834" \
  --mode light --surface "#ffffff"

[PASS] Lightness band      all 6 inside L 0.43-0.77
[PASS] Chroma floor        all 6 >= 0.1
[PASS] CVD separation      worst adjacent #008300 <-> #eda100  dE 24.2 (protan) · 21.6 (tritan)
[WARN] Contrast vs surface below 3:1: chart-2 (2.82), chart-3 (2.17)
-> ALL CHECKS PASS
```

Worst adjacent CVD ΔE is **24.2**, double the ≥12 target. Safe under protanopia and
deuteranopia.

### ⚠ BINDING CONSTRAINT — the relief rule

`--chart-2` and `--chart-3` sit below 3:1 against the white surface. Per the color
formula, **a contrast WARN is not dismissable**: it obligates a relief channel. Therefore,
non-negotiably, in this codebase:

1. Every chart with ≥ 2 series **ships a legend carrying the value**, not just the hue.
2. Every chart **ships a visually-hidden `<table>`** with the same data, exposed to
   screen readers and to the "View as table" toggle.
3. Series are **never identified by color alone** — legend swatch + text label always.

`ChartFrame` in `src/components/charts/chart-frame.tsx` enforces 1–3 structurally: it
will not render without a `series[]` (label + value) and a `tableData` prop.

### Assignment rules

- Slots are assigned **in fixed order, never cycled**. A 7th series folds into "Other".
- **Color follows the entity, not its rank.** Filtering out a series must not repaint the
  survivors. Concretely: `Voice` is always `--chart-1`, `WhatsApp` always `--chart-2`,
  `Web Chat` always `--chart-3`, regardless of which are visible. Bindings live in
  `src/components/charts/series-map.ts` — a single lookup, never inline.
- Never `--chart-N` for a series that *means* good or bad. That takes a status token.

---

## 4. NEW: sequential ramp (heatmaps)

Magnitude encoding for §6.2 bookings-by-hour and §14.1 best-contact-window heatmaps.
One hue (blue), light → dark, monotone OKLCH lightness. The lightest step means
"near zero" and is allowed to recede toward the surface, per the sequential rule.

| Token | Hex | OKLCH L |
|---|---|---|
| `--seq-1` | `#cde2fb` | 0.905 |
| `--seq-2` | `#86b6ef` | 0.764 |
| `--seq-3` | `#3987e5` | 0.622 |
| `--seq-4` | `#256abf` | 0.527 |
| `--seq-5` | `#0d366b` | 0.338 |

Monotone with ΔL of 0.141 / 0.142 / 0.095 / 0.189 — every gap clears the 0.06 floor.
Heatmap cells carry their numeric value as a direct label, so magnitude never rests on
color alone.

---

## 5. NEW: status token (amber)

| Token | Hex | Contrast | Meaning |
|---|---|---|---|
| `--status-warning` | `#fab219` | 1.83:1 | amber — SLA aging past threshold 1 (24h) |

The theme had **no amber at all**, but §8.1 requires "amber past 24 hours, red past 48
hours". Red reuses the existing `--destructive` (`#ef4444`, 3.76:1) rather than
introducing a second red.

At 1.83:1 amber is far below 3:1 **by design** — per the status rule, a status color
never carries meaning alone. `AgingBadge` always renders an **icon + text label**
("⚠ 26h in queue"), so the color is reinforcement, never the signal. Status tokens are
**reserved**: they may never be used as a categorical series.

---

## 6. What is deliberately NOT ramped

**Funnels (§13.1 eight stages, §14.1 six stages) use a single hue — `--chart-1` — for
every stage.** An ordinal ramp was attempted and rejected on evidence: the blue ladder
quantizes at ΔL ≈ 0.047, so at most 5 steps clear the 0.06 adjacent-lightness floor while
keeping the light end above 2:1 contrast. Eight stages is impossible without collapsing
adjacent steps into indistinguishability.

```
node scripts/validate_palette.js "#0d366b,#184f95,#256abf,#2a78d6,#5598e7,#86b6ef" --ordinal
[FAIL] Adjacent dL  steps too close: #256abf <-> #2a78d6 = 0.048
```

A funnel already encodes order through vertical position, monotonically shrinking width,
and stage labels. Re-encoding that in color spends the identity channel to say what
geometry already says. Stage-to-stage conversion percentages are direct-labeled instead.

---

## 7. Chart chrome

Reuses existing tokens exclusively — no new values.

| Role | Token |
|---|---|
| Chart surface | `hsl(var(--card))` |
| Gridline (hairline) | `hsl(var(--border))` |
| Baseline / axis | `hsl(var(--border))` |
| Axis labels, ticks | `hsl(var(--muted-foreground))` |
| Series label text | `hsl(var(--foreground))` |
| Target / threshold line | `hsl(var(--muted-foreground))`, dashed `4 4` |
| Event marker (§12.2) | `hsl(var(--foreground))` ring on `hsl(var(--card))` fill |

**Text wears text tokens, never the series color.** A colored swatch beside a label
carries identity; the label itself stays in `--foreground` / `--muted-foreground`.

---

## 8. Mark specs (from the dataviz skill, applied uniformly)

- 2px stroke on lines; ≥ 8px point markers.
- 4px rounded data-ends on bars, anchored square to the baseline.
- 2px surface-colored gap between stacked segments and adjacent bars.
- 2px surface ring on overlapping marks.
- Recessive grid: hairline `--border`, horizontal only, never over the marks.
- Selective direct labels — never a number on every point.
- One y-axis. **Never a dual-axis chart.** Two measures of different scale become two
  charts (this is why §4.5 "calls over time" and "minutes over time" are specified, and
  built, as two separate charts rather than one with two scales).

---

## 9. Dark mode

**Not in scope for this build.** The scaffold ships no `.dark` class and no
`prefers-color-scheme` block, and the spec never mentions dark mode. Adding one would
require re-validating all 12 new tokens against a dark surface, since a dark palette is
*selected*, never an automatic flip of the light one. Logged as a follow-up in
`BUILD_SUMMARY.md`, not silently half-implemented.
