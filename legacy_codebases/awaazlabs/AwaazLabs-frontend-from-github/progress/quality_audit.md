# §12 Quality and Optimization — self-audit

Bullet-by-bullet against spec §12.1–§12.6. Every UI element traces to a spec bullet.

## §12.1 Header: the loop, visualized
- ✅ Four-stage horizontal loop graphic (Calls completed → Analyzed and graded → Flagged for optimization → Optimizations applied) via the `LoopGraphic` primitive (`loop-header.tsx`).
- ✅ Live counts from `loopCounts(fixture, session)` — not re-derived. Per B10: flagged = `detected|in_tuning`, applied = `deployed|verified` (enforced inside `loopCounts`).
- ✅ Each stage is a click-through filter (`onStageClick`). Real behavior: stages "Flagged"/"Optimizations applied" filter the §12.4 timeline by the mapped statuses and scroll it into view; "Calls completed"/"Analyzed and graded" clear the filter and scroll to the §12.2 analytics block. A dismissible "Filtered to X · Show all" control appears on the timeline.

## §12.2 Aggregate quality
- ✅ Current quality score (0–100) via `aggregateQualityScore(scopedCalls)` — the SAME function Overview §4.4 reads (imported, never averaged inline). Rendered large as `89/100`.
- ✅ 30-day AND 90-day trend line (`Tabs` 30-day/90-day) via `LineChart`; one implementation `qualityTrend`.
- ✅ Optimization events plotted as markers on the line via `LineChart`'s `markers` prop. Marker `x` = trend-array index of the event's `deployedAtUtc` day; `label` = client-safe `whatWasChanged`.
- ✅ Seeded lift renders visibly: `opt_ns_001` deploys 20 days ago → marker at 30-day index 9, where the aggregate line steps from ~85 to ~91 (see script output below). Leading "no-data-yet" zeros from `qualityTrend` are shown as gaps, never a dive to the axis.
- ✅ Grade distribution histogram via `Histogram`. Bands: `<70 · 70–79 · 80–84 · 85–89 · 90–94 · 95–100` (see rationale below).
- ✅ Per-agent quality table: agent · calls graded · average grade · trend arrow · open optimization items.

## §12.3 Grading dimensions (per-call and aggregate)
- ✅ All five dimensions rendered with label + description (`GRADING_DIMENSIONS`, `_LABELS`, `_DESCRIPTIONS`): Accuracy · Compliance · Conversation quality · Task completion · Efficiency.
- ✅ Reusable `<GradeBreakdown grade={QaGrade} />` exported from `src/app/quality/grade-breakdown.tsx` — minimal props, self-contained (no session/fixture/hooks), for the Conversations §10.1 importer.
- ✅ Aggregate breakdown rendered on this tab through the shared component (`aggregateBreakdown`), satisfying "per-call **and aggregate**".

## §12.4 Optimization events timeline
- ✅ Reverse-chronological feed (`sortEventsNewestFirst`, by `detectedAtUtc`).
- ✅ Each entry: date · agent affected · what was detected · what was changed · status (`OptimizationStatusChip`) · grade delta (prominent, signed `+11`, only when measured).
- ✅ Client-safe language only. **No internal tuning mechanics** (prompts, model config, reviewer identity) rendered — only the controlled `whatWasDetected`/`whatWasChanged` fixture strings. The only grep hit for those words is a code comment restating the boundary.

## §12.5 Flagged interactions
- ✅ All client-submitted flags with status submitted / under review / resolved (`FlagStatusChip`) + resolution note. Priority ordering: submitted → under review → resolved, newest first.
- ✅ Each flag links to its source interaction (`/conversations/calls?interaction=…` or `/conversations/chats?interaction=…`).
- ✅ NON-PHI degraded: flag renders without the patient-identifying link (`canSeePatientRows` gate), with an explanatory note.
- ✅ Scoped to the location filter via the source interaction's location.

## §12.6 Compliance sub-panel — exactly three rate metrics
- ✅ Clinical boundary adherence rate — mean of grading dimension two (Compliance) across graded calls; target 100% shown.
- ✅ Disclosure delivery rate — consent disclosures delivered on recorded two-party-consent calls (loc_north).
- ✅ Escalation correctness rate — escalations with a canonical trigger routed to a destination / all escalations in scope.
- ✅ Exactly three metrics, no more. Non-derivable in a given scope → "N/A" (never fabricated).

## Degraded states
- ✅ NON-PHI: tab is aggregate; all rates/charts compute from the fixture; flag links withheld.
- ✅ Cedar org (`optimizationEvents: []`, `flags: []`): timeline and flags show `EmptyState`; loop renders with zero counts (no crash); trend/histogram render from Cedar's graded calls; disclosure & escalation rates → N/A (one-party, no escalations).

## Grade-distribution bands — rationale
`<70 · 70–79 · 80–84 · 85–89 · 90–94 · 95–100`. A wide failing tail below 70, then 5-point bins across the band where clinic calls actually land (78–96 in the fixture), so the deployment lift visibly moves calls out of 80–84 into 90–94.

## §12.6 derivations (stated per instruction)
1. **Clinical boundary adherence** = round(mean(`grade.breakdown.compliance`) over scoped graded calls). Fixture ⇒ ~89. The spec's "share of clinical questions correctly routed" is realized via the Compliance dimension exactly as §12.6 directs ("sourced from grading dimension two"); the Compliance dimension's own definition is "clinical boundary respected". Target line shown at 100%.
2. **Disclosure delivery** = round(calls with `media.consentDisclosureAtUtc` present ÷ recorded calls at two-party-consent locations). Only `loc_north` is two-party; every recorded loc_north call carries the disclosure ⇒ 100%.
3. **Escalation correctness** = round(escalations with a canonical `trigger` and a non-empty `routedTo` ÷ scoped escalations). The fixture seeds **no** mis-triggered escalation, so this is honestly 100% — not invented. Documented rather than manufactured.

## Verification script output (proof of the seeded lift)
```
=== Aggregate quality score (Overview §4.4 == Quality §12.2) ===
aggregateQualityScore(scopedCalls) = 89

=== 30-day quality trend array ===
[0,0,0,86.5,85.5,80,89,83,88.5,87,91.5,91,94.5,92,89.3,88,93.5,91.3,92.3,90.8,92.3,91.3,91.3,88.7,90,90.8,92.1,90.6,92.3,91]

=== opt_ns_001 (receptionist closing sequence) ===
status = verified · gradeDelta = 11 · deployedAtUtc = 2026-06-19T15:20:00.000Z

=== Receptionist mean grade before vs after deploy ===
before deploy: n = 27  mean = 82.15
after  deploy: n = 58  mean = 91.62
lift          = 9.47 points
```
Deploy is 20 days ago → 30-day marker index 9; the aggregate line steps from ~85 (indices 3–9) to ~91–92 (indices 10+) right at the marker.

## Checks
- `npx tsc --noEmit` → NO ERRORS IN src/app/quality/ (one unrelated pre-existing error in `src/app/agents/vob/vob-analytics.ts`, another agent's file).
- color literals grep → EMPTY. `: any` / `as any` grep → EMPTY.
- tuning-mechanics grep → only a code comment restating the boundary (not user-visible).
- `aggregateQualityScore` imported from `@/lib/metrics` and called (not averaged inline).
- `npx eslint src/app/quality/` → clean.
