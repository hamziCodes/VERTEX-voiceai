# UI Primitives Audit

Shared UI primitive library for the AwaazLabs Client Dashboard. Every color is a
token-bound Tailwind class or `var(--…)`; no literal colors, no `any`, no
`dangerouslySetInnerHTML`. All files live under `src/components/ui/`.

Legend: ✅ met · ⚠️ met with a noted interpretation · ❌ not met

---

## Repaired

### `table.tsx` — §5.2, §7.2, §8.1, §10.1, §11.1, §12.2, §14.2, §16.2
- ✅ D1 fixed: `[&amp;_tr]:border-b` → `[&_tr]:border-b`, `[&amp;_tr:last-child]:border-0` → `[&_tr:last-child]:border-0`.
- ✅ `scope="col"` added on `<th>` (`TableHead`).
- ✅ Optional `caption` prop, rendered `sr-only` by default (`captionSrOnly`), visible `TableCaption` retained.
- ✅ Existing visual language preserved (row hover, padding, text sizes unchanged).

### `card.tsx` — every route
- ✅ Verify-only, unchanged. `text-card-foreground` now resolves (`--card-foreground` defined in globals.css / THEME_NOTES §2). No edit made.

### `tabs.tsx` — §10 sub-views, 7D/30D toggles
- ✅ D5 fixed: `role="tablist"` / `role="tab"` / `role="tabpanel"` with `aria-selected`, `aria-controls`, `aria-labelledby`.
- ✅ Roving tabindex (active `0`, rest `-1`).
- ✅ Arrow-key navigation Left/Right/Home/End with automatic activation.
- ✅ `useMemo` deps corrected; `setValue` stabilized with `useCallback` and included in deps.
- ✅ Visual classes identical to the original.

### `badge.tsx` — status chips
- ✅ 4 existing variants kept (secondary, outline, destructive, default).
- ✅ Added `warning` variant using `bg-status-warning` (`var(--status-warning)`), dark `text-foreground` for legibility (amber 1.83:1 never carries meaning alone).

### `button.tsx` — everywhere
- ✅ 4 variants kept; `md` size preserves original padding (default appearance unchanged).
- ✅ Added `size?: 'sm' | 'md'`, `aria-label` passthrough, `title`, and `React.forwardRef<HTMLButtonElement>`.

---

## Created

### `status-chip.tsx` — §5.2, §6.2, §4.2, §7.3, §10.1, §11.1, §12, §13, §14, §15
- ✅ 10 discrete chips, each typed to its canonical union (not `string`).
- ✅ Labels sourced only from `*_LABELS` maps; none hardcoded.
- ✅ Appointments VOB chip uses `VOB_CHIP_LABELS` (`abbreviated` prop), falling back to full label where the Partial map is silent.
- ✅ Red accent (`destructive`) on triage High/Urgent and on VOB needs-attention states.
- ⚠️ Non-mandated statuses render neutral (`secondary`) rather than inventing unvalidated color meaning (interpretation noted below).

### `stat-card.tsx` — §4.1–4.5, every agent tab
- ✅ `label`, `value`, `format`; `delta` with `deltaIsGood` (bad→red, good→neutral foreground, unset→muted); `tooltip`; `accent`; `href` (whole-card link overlay + focus ring); `chart` node slot; `subStats`.
- ✅ Numbers use `tabular-nums`.
- ⚠️ No green "good" color: the theme has no success token, so a good delta stays neutral foreground; only bad movements are colored (red).

### `drawer.tsx` — §5.4, §8.2, §10.1, §10.2
- ✅ Radix Dialog: focus trap, ARIA, Escape, focus restore. Right slide-over, `max-w-[640px]`, scrollable body, sticky header with title + close, optional footer/trigger/description.

### `tooltip.tsx` — stat-card info icons
- ✅ Hand-rolled; opens on hover AND keyboard focus (never hover alone); Escape closes; trigger is a real focusable button with `aria-label`; content `role="tooltip"` + `aria-describedby`.

### `banner.tsx` — §4.6, §5.6
- ✅ Dismissible (`onDismiss`, dismissal state left to caller); `destructive` / `default` variants; `role="alert"`/`"status"`; icon; supports deep-link children.

### `masked-value.tsx` — §5.2, §10.1, §14.2 (SECURITY-CRITICAL)
- ✅ Renders `phoneMasked` by default.
- ✅ Reveal control shown only when `identity.phoneE164 !== null` (structural, no local role check).
- ✅ Reveal calls `revealPhone(identity, session, objectRef)` (audit written by data layer).
- ✅ `try/catch` for `PermissionDeniedError` → non-leaking message.
- ✅ Reveal button `aria-label="Reveal phone number for {firstName} {lastName}"`.

### `aging-badge.tsx` — §8.1, §4.6, §11.2
- ✅ Thresholds from `VOB_AGING_THRESHOLD_HOURS` (24/48 never hardcoded).
- ✅ Amber never alone: always icon + text label (`26h in queue`).

### `empty-state.tsx` — §5.6, every table
- ✅ Icon + headline + body + optional action.

### `under-construction.tsx` — Milestone-1 stubs
- ✅ Props `section`, `specRef`, `plannedFor`, `description`; polished, intentional (labeled "Under construction", states spec + timing + contents).

### `page-header.tsx` — every route
- ✅ Title + optional description + optional right-slot actions.

### `select.tsx` — every filter bar
- ✅ Radix Select wrapper matching input/button visual language (`border-input`); keyboard nav + ARIA from Radix; focusable trigger with `aria-label`.

---

## Interpretations chosen (narrowest)

1. **Status-chip colors** — the spec mandates red in exactly two places (triage High/Urgent; VOB needs-attention). All other statuses render neutral `secondary` to avoid introducing unvalidated color semantics that THEME_NOTES would forbid.
2. **VOB needs-attention set** — used `isVobNeedsAttention` (§7.3: terminal and not `verified`), which is the general worklist definition and a superset of the §4.2 Overview trio, so both are covered.
3. **StatCard "good" delta** — no success/green token exists in the theme; a good delta renders neutral foreground and only bad deltas are colored (red). Card link is an `absolute inset-0` overlay so the tooltip button is never nested inside an anchor (valid HTML).

---

## Verification (actual output)

1. `npx tsc --noEmit` — zero errors originating in `src/components/ui/*` (remaining errors are in `.next/types`, `src/app/*` mid-rewrite, and the frozen `src/shared/session-context.tsx`).
2. `grep -rniE "#[0-9a-f]{3,8}\b|rgb\(|rgba\(" src/components/ui/` → **no output**.
3. `grep -rn ": any\|as any" src/components/ui/` → **no output**.
4. `grep -rn "amp;" src/components/ui/` → **no output** (D1 fixed).
