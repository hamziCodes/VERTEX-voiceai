# VOB Queue (§8) + VOB Agent (§7) — Part D self-audit

Bullet-by-bullet against the spec. ✅ done · ⚠️ done with a noted interpretation · ❌ not done.

Every UI element below traces to a spec bullet. Statuses import from `src/shared/status-models.ts`
(§7.3); none are re-declared. No color literals, no `any`.

---

## §7 — VOB AGENT TAB (analytics) — `src/app/agents/vob/`

### §7.1 Stat cards
- ✅ Verifications (count) with **period selector** — `Select` in the page header (7/30/90/All), scopes every card.
- ✅ Verified rate %.
- ✅ Partial coverage · Needs authorization · Needs referral · Not covered · Inactive policy · Unable to verify — each a **% with count on hover** via `StatCard.tooltip` (uses the `Tooltip` primitive), text `N of M terminal verifications`.
- ✅ Prior auth required % — with the revenue-protection note in its tooltip.
- ✅ Referral required %.
- ✅ IVR navigation success % (denominator = records with ≥1 attempt).
- ✅ **Benefit capture completeness, decomposed into THREE sub-bars** (copay / deductible / OOP-max) — `BenefitCaptureBars`, three labelled bars with a dashed 95% target marker. Never one number.
- ✅ Member not found (count and share) — count as the value, share as a sub-stat.
- ✅ Payer reps reached (count).
- ✅ **Average handle time per call, PLUS turnaround per verification (request→terminal), median and P95** — three separate labelled cards: Avg handle time, Turnaround (median), Turnaround (P95).

### §7.2 Charts
- ⚠️ **VOB status distribution horizontal bars, sums to 100%** — `DistributionBar` over the three color-safe groups (In progress / Verified / Needs attention) from `series-map.ts`. Interpretation: the frozen palette cannot give 8 statuses distinct compliant colors (categorical excludes red; the 7 non-verified terminals all "mean bad" → would be one red blob). The three-group render mirrors §4.2; the **full per-status breakdown is carried in the ChartFrame relief table** (columns Status/Count).
- ✅ Verifications over time — `LineChart`, terminal verifications per week over 8 weeks, single `--chart-1` series.
- ✅ **Payer breakdown table — made prominent**: `PayerBreakdownTable` in its own full-width `border-2` card with an `text-xl` heading, per payer verification count / verified rate / avg handle time / unable-to-verify rate, **sorted by unable-to-verify rate DESC** so problem payers surface first; problem payers (≥15%) get a red accent.

### §7.3 Canonical status model
- ✅ Imported from `status-models.ts`. Same record → same chip via `VobStatusChip` on Overview, VOB Agent, VOB Queue, and the Appointments column. No status string re-declared.

## Degraded state
- ✅ VOB Agent survives NON-PHI: it reads non-PHI `VobRecord` fields via `scopeToLocation(fixture.vobRecords)`, never `listVobRecords`, so it does not degrade to aggregate.

---

## §8 — VOB QUEUE (worklist) — `src/app/vob-queue/`

### §8.1 Worklist table — exactly 10 columns
`patient name · payer · plan · status · linked appointment date · assigned-to · age in queue · last attempt timestamp · attempts count · location`
- ✅ All 10 present, in order (`VobWorklistTable`). (An 11th leading checkbox column appears only for workflow-capable roles, for bulk-retry selection per §8.4 — not a data column.)
- ✅ **Aging SLA** via `agingLevel(record)` + `AgingBadge`; amber 24h / red 48h from `VOB_AGING_THRESHOLD_HOURS` (never hardcoded). `agingLevel` gates whether the badge shows; `AgingBadge` always renders icon + text (amber is 1.83:1).
- ✅ **`?filter=needs-attention`** read with `useSearchParams()` and pre-applied (`isVobNeedsAttention`); a removable chip lets the user clear it. `page.tsx` wraps the client in `<Suspense>` (Next 15 requirement).

### §8.2 Row detail drawer — `VobDetailDrawer`
- ✅ Captured benefits (copay, deductible, OOP, coverage notes).
- ✅ Prior auth & referral flags (badges + fields).
- ✅ Per-attempt call log with recordings + transcripts — media resolved through `listCalls` projection; a Viewer/NON-PHI session receives `media: null`, so **nothing** is rendered (no disabled player). Playback/transcript call `playRecording`/`viewTranscript` (audited).
- ✅ Payer reference numbers per attempt.

### §8.3 Row actions — all four, each audited + updates the status timeline
- ✅ **Retry** — `recordVobQueueAction(session, id, 'retry')`, optimistically re-queues + timeline entry.
- ✅ **Mark resolved** with **reason picker** (`VOB_RESOLVE_REASONS`) — `recordVobQueueAction(…, 'resolve', {reason})`, timeline entry, row leaves worklist.
- ✅ **Escalate to staff** (assigns) — `recordVobQueueAction(…, 'escalate', {assignee})`, sets assignee + timeline entry.
- ✅ **Add note** — `recordVobQueueAction(…, 'add_note')`, appends note + timeline entry.
- ✅ Gated on `canPerformWorkflowActions` — a Viewer sees no actions block. Timeline updates are optimistic local state (fixture read-only; timestamps use `mockNow()`, never `Date.now()`).

### §8.4 Queue-level controls — `VobFilters`
- ✅ Filters by status, payer, age, assigned-to, location (location filter shown only for multi-location orgs).
- ✅ **Bulk retry on filtered selection** (checkbox column + "Retry selected (n)"), gated on `canPerformWorkflowActions`.
- ✅ **CSV export (audited, role-gated)** — `recordExport(session, 'vob_queue', rowCount, filters)` (throws `PermissionDeniedError` for a Viewer), Blob download client-side. Export button rendered only when `canExport`.
- ✅ **Phone-leak guard**: `buildVobCsv` reads only the projected `VobRowVM` and uses `identity.phoneMasked`; `phoneE164` is never referenced in the export path, so an unrevealed phone exports as its mask.

## Degraded states
- ✅ NON-PHI: `listVobRecords` → `{kind:'aggregate'}` → aggregate count card, table hidden.
- ✅ Viewer: no action buttons, no bulk retry, no export button, no phone reveal, no recordings/transcripts (media null).
- ✅ Cedar org (3 records, `appointmentId: null`): linked-appointment column shows `—`, single-location filter hidden, nothing crashes.
- ✅ Empty state: `EmptyState` when filters yield no rows.

---

## Verification
- `npx tsc --noEmit` → 0 errors.
- `npx eslint src/app/vob-queue src/app/agents/vob` → clean.
- color-literal grep → empty; `: any`/`as any` grep → empty.
- status-literal grep hits are all comparisons/assignments against the imported `VobStatus` union or the spec-listed `satisfies VobTerminalStatus[]` subset — no redeclared enum.
