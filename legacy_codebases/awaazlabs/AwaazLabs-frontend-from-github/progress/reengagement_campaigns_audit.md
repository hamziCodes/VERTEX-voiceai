# §14 Reengagement + Campaigns — Part D self-audit

Bullet-by-bullet against spec §14.1 and §14.2. ✅ done · ⚠️ done with a documented
interpretation · ❌ not done.

## Files created

| File | Purpose |
|---|---|
| `src/app/(dashboard)/agents/reengagement/page.tsx` | §14.1 route → client |
| `src/app/(dashboard)/agents/reengagement/reengagement-client.tsx` | §14.1 tab, renders through `AgentAnalyticsPage` |
| `src/app/(dashboard)/agents/reengagement/reengagement-analytics.ts` | Shared funnel builder, stats, heatmap (pure) |
| `src/app/(dashboard)/campaigns/page.tsx` | §14.2 route → client |
| `src/app/(dashboard)/campaigns/campaigns-client.tsx` | §14.2 campaign list + detail drawer |
| `src/app/(dashboard)/campaigns/campaign-detail.tsx` | §14.2 detail: funnel, audience, contacts, pacing, guardrails, controls |
| `src/app/(dashboard)/campaigns/request-audience-form.tsx` | §14.2 request-to-Awaaz stub |
| `src/app/(dashboard)/campaigns/campaign-labels.ts` | Display labels for the campaign TYPE enum (no frozen label map exists) |

## §14.1 Reengagement (agent analytics, §2.6 template)

- ✅ Renders through the §2.6 template (`AgentAnalyticsPage`) — stats, primaryChart (funnel), distribution (heatmap), drillThrough.
- ✅ Funnel: SIX stages, single hue (via `Funnel`, which is hard-coded to `var(--chart-1)`), per-stage count + stage-to-stage conversion %. Stages: **audience → contacted → reached → conversation completed → booking intent → booked**.
- ✅ Stat card: Contacts attempted · reached · reach rate.
- ✅ Stat card: Conversations completed.
- ✅ Stat card: Bookings generated (count + conversion rate from reached, as a subStat).
- ✅ Stat card: Revenue estimate from reengagement bookings — reads `reengagementBookings` and `avgAppointmentValueUsd` from `revenueRecoveredEstimate`; value = `reengagementBookings × avgAppointmentValueUsd`.
- ✅ Revenue card **hides** when `revenueRecoveredEstimate` returns `null` (org has no avg value — Cedar).
- ✅ Stat card: Opt-outs generated (tooltip notes the auto-write to suppression).
- ✅ Stat card: Average attempts per successful booking.
- ✅ Best contact window: reach rate by hour-of-day × day-of-week `Heatmap`; every cell carries its numeric % as a direct label.
- ✅ Drill-through: `/conversations/calls?agent=reengagement`.
- ⚠️ Funnel-stage derivation from the §17 campaign-contact status model. The six status states do not map one-to-one onto the six funnel stages. Documented mapping (monotonic, not fabricated): audience = contacts entered; contacted = attempts > 0; reached = {reached, opt_out, booked}; conversation completed = {reached, opt_out, booked}; booking intent = {reached, booked}; booked = {booked}. This yields one legitimate 100 % step (reached → conversation completed) rather than fabricating a distinction the data does not carry. Northside reengagement funnel: 9 → 8 → 6 → 6 → 5 → 4.

## §14.2 Campaigns (GROWTH tab — not the agent template)

- ✅ Does **not** render through the §2.6 template (bespoke list + detail).
- ✅ Renders all outbound types (reengagement, no-show recovery, recall).
- ✅ Campaign list columns, exactly: name · type · audience size · status · started · progress (contacted ÷ audience) · bookings to date · location.
- ✅ Status chip via `CampaignStatusChip` (imported `CAMPAIGN_STATUS_LABELS`, never redeclared).
- ✅ Campaign detail: funnel **identical to §14.1** — literally the same `reengagementFunnel` + `funnelTableData` functions, scoped to the campaign.
- ✅ Audience definition summary from `campaign.audienceDefinition`.
- ✅ Per-contact rows: name · phone masked (`MaskedValue` with `session` + `objectRef`) · attempts · last outcome · booked link · opt-out flag. No local role check on the reveal control — trusts `identity.phoneE164 === null` omission.
- ✅ Pacing settings display (read-only): calling window (+ location timezone), max attempts, retry spacing.
- ✅ Guardrails read-only panel: suppression check, TCPA window, per-contact attempt cap.
- ✅ Pause/resume controls gated on `canControlCampaigns(session)`; visible only for running/paused campaigns.
- ⚠️ **Audit event for pause/resume**: §2.3 enumerates exactly twelve `AuditEventType`s and none is truthful for a campaign pause/resume. Following the task instruction and the BUILD_NOTES.md B14 precedent (the Flag button), **no audit event is written and no thirteenth type is added**. Fabricating an audit row with an unrelated type would be worse than none (per audit.ts's own "a fabricated audit field is worse than an honest one"). The controls change local state only. Recorded here explicitly.
- ✅ Request-audience: a **request stub** (short form → confirmation), gated to non-Viewers. **No self-serve segment builder** was built — the spec defers it.
- ⚠️ "Progress (contacted ÷ audience)": denominator is contacts entered into the pipeline (the funnel's audience stage), not the configured `audienceSize`. Using `audienceSize` (140/32/88) against the tracked-contact sample would render a *completed* campaign at ~8 % progress — misleading. The list still shows `audienceSize` in its own "Audience size" column per spec; a footnote states the distinction.

## Degraded / empty states

- ✅ NON-PHI: §14.1 is aggregate and unaffected. §14.2 detail hides per-contact rows via `canSeePatientRows`, showing an aggregate-count EmptyState; funnel + columns still render.
- ✅ Viewer: no pause/resume (`canControlCampaigns`), no request-audience button (`role !== 'VIEWER'`), no phone reveal (structural via `MaskedValue`).
- ✅ Cedar (`org_cedar`): `campaigns: []` → EmptyState on both tabs; `avgAppointmentValueUsd: null` → revenue card hidden; §14.1 isEmpty → template EmptyState. No crash, no divide-by-zero (`ratio()` used for every rate).
- ✅ Every rate uses `ratio()` and renders `—` for a null denominator, never `NaN` or a misleading `0%`.

## Theme / mechanical checks

- ✅ No literal colors (`grep` empty). No `any` / `as any` (`grep` empty). No new packages, no `dangerouslySetInnerHTML`.
- ✅ Funnel single hue (delegated to `Funnel`); heatmap uses the sequential ramp with numeric cell labels (delegated to `Heatmap`).
- ✅ Every chart renders through its primitive → `ChartFrame` with `tableData` supplied.
- ✅ `npx tsc --noEmit` clean; `npx eslint` clean on both folders.
- ✅ No UI element in scope lacks a traceable spec bullet.
