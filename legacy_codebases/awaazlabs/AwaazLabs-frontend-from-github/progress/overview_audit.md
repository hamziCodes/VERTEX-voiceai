# Overview tab (§4) — Part D self-audit

Bullet-by-bullet trace of §4.1–§4.6 to the built UI. Every rendered element maps to a spec
bullet; nothing exists that cannot be traced.

Files owned:
- `src/app/page.tsx` — server component, renders `<OverviewClient />`.
- `src/app/overview-client.tsx` — orchestrator; reads all metrics, hands them to sections.
- `src/app/overview/lib.ts` — Overview-local time-series buckets (no cross-tab number).
- `src/app/overview/range-tabs.tsx` — 7D/30D toggle built on the `Tabs` primitive.
- `src/app/overview/sections/{attention-banner,appointments-section,vob-section,revenue-section,quality-section,telemetry-section}.tsx`

Section order rendered: F (banner, above A) → A → B → C → D → E. Matches §4.

---

## §4.1 Section A — Appointments

- ✅ Card 1 "Booked today" — `appointmentStats.bookedToday`; delta = `bookedToday − bookedSameWeekdayLastWeek`, caption "vs same weekday last week"; href `/appointments`.
- ✅ Card 2 "Booked this week" — `bookedThisWeek`; booking rate `bookingRateThisWeek` as a sub-stat; href `/appointments`.
- ✅ Card 3 "Upcoming next 7 days" — `upcomingNext7Days`; href `/appointments?filter=upcoming`.
- ✅ Card 4 "No-shows & cancellations this week" — `noShowsAndCancellationsThisWeek` + `noShowCancelRateThisWeek`; **hidden entirely when `org.outcomeDataAvailable === false`** (B9). Verified hidden on Cedar.
- ✅ Chart "Bookings over time" — `BarChart variant="stacked"`, 7D/30D via `RangeTabs` (`Tabs`), stacked by `BOOKING_CHART_SOURCES` (Voice/WhatsApp/Web Chat) coloured from `SOURCE_SERIES`. Honest `tableData` built from the same day buckets; footnote explains Form exclusion.

## §4.2 Section B — VOB status

- ✅ Card 1 "VOB in progress" — `vobCounts.inProgress`; sub-stats queued/dialing/on call/pending callback from `inProgressBySubStatus`; href `/agents/vob`.
- ✅ Card 2 "VOB completed this week" — `completedThisWeek`; sub-stats completed today + verified rate (`verifiedRateThisWeek`); href `/agents/vob`.
- ✅ Card 3 "Needs attention" — `overviewNeedsAttention` (§4.2 trio); `accent="destructive"`; href `/vob-queue?filter=needs-attention`.
- ✅ Component — `DistributionBar compact` grouped by `vobStatusGroup` (verified/pending/needs_attention), mirroring the VOB tab (§7.2). ⚠ Deliberate: the bar's needs_attention group uses the broader §7.3 definition, distinct from the card's narrow trio — documented in status-models and series-map, not silently reconciled.

## §4.3 Section C — Revenue recovered (estimate)

- ✅ Single card — `revenueRecoveredEstimate`; **whole section hides when it returns null** (avg value unset). Verified hidden on Cedar.
- ✅ Labelled an estimate ("Estimated revenue recovered this month" / heading "(estimate)").
- ✅ Tooltip shows the formula and its live inputs, and states the "recovered no-show" definition from BUILD_NOTES B5 verbatim.
- ✅ Card links to Organization settings (`/settings/organization`) where the value is configured.

## §4.4 Section D — Quality pulse

- ✅ One row/card: aggregate grade rendered `NN/100` from `aggregateQualityScore(fixture.calls)`; 30-day sparkline from `qualityTrend(fixture.calls, 30)` in StatCard's `chart` slot; `optimizationEventsThisMonth(fixture)` as a sub-stat.
- ✅ Click-through to `/quality`. Equals the Quality tab's number by construction — same functions, same arguments; not recomputed.

## §4.5 Section E — Operational telemetry

- ✅ Interactions row — per-agent counts (voice calls per agent; Chat agent = chat sessions) plus **Overall** and **All**. ⚠ Interpretation (documented in the section header): "Overall" = all voice calls (sum of voice-agent tiles), "All" = every interaction across channels (voice + chat). Both scoped to the location filter per §2.4. Narrowest self-consistent reading of an ambiguous bullet.
- ✅ Calls today, minutes today, average duration, average cost per interaction — all from `telemetry`.
- ✅ Calls over time AND minutes over time — TWO SEPARATE `LineChart`s, one y-axis each, shared 7D/30D toggle. Never a dual axis.
- ✅ Average first-audio response — third `LineChart` with `targetLine` at `FIRST_AUDIO_TARGET_MS` (800 ms).
- ✅ Success rate — `successRate` with completion counts (`completedCount / attemptedCount`) as a sub-stat.
- ✅ Live calls now — `liveCallsNow` with refresh timestamp (`As of …`, rendered in the location tz, or UTC when unfiltered).

## §4.6 Section F — Attention banner

- ✅ Renders ABOVE Section A; dismissible; `variant="destructive"`.
- ✅ Conditional on the exactly-four triggers from `attentionConditions` (escalation aging, VOB aging >48h, line health failing, usage ≥90%).
- ✅ Each item deep-links via the `href` the metric returns (`/escalations`, `/vob-queue`, `/settings/lines`, `/settings/billing`).
- ✅ Empty array → renders nothing. Verified nothing on Cedar.

---

## §4 header requirements

- ✅ "Every card is a click-through" — every `StatCard` carries an `href` to the owning tab.
- ✅ Section order: business outcomes first, telemetry second.

## NON-PHI degradation

- ✅ Overview is aggregate-only; no patient name, phone, recording, or transcript is rendered in either mode. All numbers derive from fixture aggregates through `metrics.ts`, which are mode-independent. No section becomes blank in NON-PHI, so no "empty in NON-PHI" notice is needed.

## Empty / degraded states (Cedar `org_cedar`)

- ✅ Revenue card hides (avg value null).
- ✅ No-show card hides (`outcomeDataAvailable: false`).
- ✅ Location filter hidden (shell-owned; single-location org).
- ✅ Banner renders nothing (no qualifying conditions).
- ✅ No chart crashes on empty arrays (day-labelled x-axes always present; `appointments: []` yields all-zero bars).

## Checks

- ✅ `npx tsc --noEmit` → exit 0, zero errors.
- ✅ No literal colors / no `any` in owned files (grep empty).
- ✅ Cross-tab numbers consumed from `metrics.ts`; none re-derived.
