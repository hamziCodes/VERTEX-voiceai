# §6 Receptionist & §9 Chat Agents — self-audit

Both tabs render through the §2.6 standard template (`AgentAnalyticsPage`). Aggregate by
nature; verified no patient name / phone / recording / transcript is read in either mode.
Every rate is computed with `ratio()` → `null` (rendered `—`) when its denominator is zero,
so Cedar's near-empty org never shows NaN or a misleading 0%.

Files created:
- `src/app/(dashboard)/agents/receptionist/receptionist-analytics.ts` (~300 lines)
- `src/app/(dashboard)/agents/receptionist/receptionist-client.tsx` (~270 lines)
- `src/app/(dashboard)/agents/receptionist/page.tsx` (rewritten stub → real page)
- `src/app/(dashboard)/agents/chat/chat-analytics.ts` (~250 lines)
- `src/app/(dashboard)/agents/chat/chat-client.tsx` (~260 lines)
- `src/app/(dashboard)/agents/chat/containment-resolution-pair.tsx` (~45 lines)
- `src/app/(dashboard)/agents/chat/page.tsx` (rewritten stub → real page)

## §6.1 Receptionist stat cards (all eight)

- ✅ Appointments booked — count, with completed inbound calls as a shown sub-stat denominator.
- ✅ Booking rate % — with the ~75% healthcare scheduling FCR benchmark in the tooltip (and a benchmark sub-stat).
- ✅ Safety escalation rate % — triage High + Urgent share of Receptionist calls; tooltip explains the four-level triage model.
- ✅ Insurance capture rate % — tooltip notes front-end capture reduces downstream denials.
- ✅ WhatsApp deflection-suitable rate % — ⚠️ interpretation (info-only completed inbound calls / completed inbound calls); definition stated in the tooltip so it is not mistaken for actual WhatsApp volume.
- ✅ Average booking handle time — mean duration of Receptionist calls that ended in a booking.
- ✅ After-hours share of bookings — labelled "the recovery story rendered as a metric"; reads `afterHours`.
- ✅ Missed and abandoned inbound — inbound legs that ended before agent connect (abandoned + no answer); red accent when > 0; target near zero.

## §6.2 Charts and distributions

- ✅ Triage distribution donut (None, Low, High, Urgent) — colors from canonical `TRIAGE_SERIES`.
- ✅ Intake method donut (Form, Voice, Unknown) — ⚠️ colors via a local `INTAKE_METHOD_SERIES` (no series-map entry exists; series-map is frozen). Token-only, single lookup keyed by entity.
- ✅ Language mix horizontal bars (en, es, other) — `DistributionBar`; local `LANGUAGE_SERIES`, token-only.
- ✅ Bookings by hour-of-day heatmap split business vs after hours — `Heatmap` with `columnGroups` (Before open / Business hours / After close); day-of-week × hour, local time, from `bookedAtUtc`.
- ✅ Booking rate trend, 7D/30D — `LineChart` with a `Tabs` toggle; daily rate, gap (null) on days with no denominator.

## §6.3 Drill-through

- ✅ `/conversations/calls?agent=receptionist` via the template's drill-through slot (label scoped to the agent).

## §9.1 Chat stat cards

- ✅ Sessions — count with period selector (header `Select`), split into WhatsApp / Web Chat sub-stats.
- ✅ Average messages per session.
- ✅ Containment rate % + Resolution rate % — rendered via `ContainmentResolutionPair` (see below).
- ✅ Deflection rate — ⚠️ interpretation (contained + resolved) / total, distinct from containment/resolution; tooltip states it.
- ✅ Escalation rate — neutral accent; explicitly framed as a legitimate outcome, not a failure.
- ✅ Bookings from chat — count + conversion (bookings ÷ booking-intent sessions).
- ✅ Average + P95 response latency — one card, target sub-stat `< 800 ms` using `FIRST_AUDIO_TARGET_MS`.
- ✅ CSAT proxy out of 5 — ⚠️ proxy = mean QA grade / 20; tooltip states the derivation.

## §9.1 paired reading rule (how it is rendered — the load-bearing bullet)

- ✅ `containment-resolution-pair.tsx` renders a single `<figure className="sm:col-span-2">` that
  lives **inside** the template's stat grid, holding the two `StatCard`s in an inner
  `grid sm:grid-cols-2` (so they sit adjacent) with **one shared `<figcaption>`** below both:
  "Read these two together. High containment with low resolution is *false containment* — the
  agent held the conversation but did not meet the patient's goal." They are therefore never
  two unrelated cells in the 4-column grid.

## §9.2 Charts

- ✅ Containment vs Resolution vs Deflection vs Escalation — `BarChart variant="grouped"`, colors from `CHAT_METRIC_SERIES`; escalation uses its categorical chart token (chart-4), not a status/failure color.
- ✅ Sessions over time by channel — `BarChart variant="stacked"` by week, `CHAT_CHANNEL_SERIES`.
- ✅ Intent distribution donut (booking, pricing, hours & directions, insurance question, clinical question routed, other) — local `CHAT_INTENT_SERIES` (six intents, fixed slot order chart-1..6).
- ✅ Language mix — `DistributionBar`, local `LANGUAGE_SERIES`.

## §9.3 Drill-through

- ✅ `/conversations/chats` via the template's drill-through slot.

## Degraded / empty states

- ✅ Both tabs read only aggregate fields — no PHI surface in either mode.
- ✅ Cedar (org_cedar): 0 appointments, 6 calls, 4 chats. Receptionist renders (3 Receptionist calls) with booking-related rates as `—`; Chat renders 4 sessions. No division by zero anywhere (`ratio()` + explicit `> 0` guards on averages).
- ✅ `isEmpty` + `emptyState` wired: Receptionist when it has neither a booking nor a call in scope; Chat when the period-filtered set is empty.
- ✅ Donuts/distribution bars handle total = 0 (empty ring / muted bar); heatmap handles all-null.

## Color-token correctness (the black-fill bug guard)

- ✅ Chart-series colors use complete-value tokens bare (`var(--chart-n)`, `var(--chart-5)` …).
- ✅ Chrome/neutral colors use HSL-triple tokens wrapped (`hsl(var(--muted-foreground))`). No bare base-UI token in any `fill`/`color`. Verified by grep.

## Deviations / narrowest interpretations chosen

- Categorical color maps for intake method, language, and chat intent live as module-level
  const lookups in the two owned analytics files (keyed by entity, token-only, never inline),
  because `series-map.ts` is frozen and has no entry for these dimensions. This honors the
  "color follows the entity, never inline" rule within the constraint that series-map cannot
  be edited.
- WhatsApp-deflection-suitable, chat deflection rate, and CSAT proxy have no direct fixture
  field; each uses the narrowest defensible definition, stated in its card/tooltip.

## Checks

- `npx tsc --noEmit` → zero errors in receptionist/chat files (the one repo error is in
  `review-taker`, another agent's concurrent file).
- literal-color grep → empty. `: any` / `as any` grep → empty.
- `npx eslint` on both folders → clean.
