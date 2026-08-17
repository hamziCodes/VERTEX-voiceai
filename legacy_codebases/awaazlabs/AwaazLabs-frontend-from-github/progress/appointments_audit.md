# Appointments tab — self-audit (spec §5)

Bullet-by-bullet trace of §5.1–§5.6. Legend: ✅ done · ⚠️ done with a noted interpretation · ❌ not done.

Files (all under `src/app/appointments/`, the only files touched):
- `page.tsx` — server wrapper
- `appointments-client.tsx` — orchestration, modes, banners, stats strip, tabs, drawer state
- `appointments-filters.tsx` — §5.3 filter bar
- `appointments-table.tsx` — §5.2 table
- `appointments-calendar.tsx` — §5.5 calendar/agenda
- `appointment-drawer.tsx` — §5.4 drawer
- `types.ts` — shared filter/sort types + date-key helpers

No frozen file was modified. No color literal, no `any`, no `dangerouslySetInnerHTML`, no new package.

## §5.1 Header stats strip
- ✅ Booked today, Upcoming next 7 days, Confirmation rate, No-show rate (trailing 30 days).
- ✅ All values come from `appointmentStats(fixture, session)`; nothing is recomputed locally.
- ✅ Rendered in every mode (aggregates are allowed in NON-PHI). Null rates render as `—`.

## §5.2 Table — 12 columns (BUILD_NOTES B4)
Column count stated explicitly: **12**. Eleven always render; **Location is the 12th and renders only when `isMultiLocation(org)`**. There is no 13th column (the guide's "13" is a miscount, per B4).

1. ✅ Date and time — location timezone via `formatDateTime`/`timezoneFor`; **default sort upcoming ascending** (`DEFAULT_SORT = datetime asc`); sortable.
2. ✅ Patient name (first + last); sortable by last, first.
3. ✅ Phone — `<MaskedValue identity session objectRef={`appointment:${id}`} />`. No local role check; a Viewer receives `phoneE164: null`, so no reveal control renders.
4. ✅ Treatment or service interest.
5. ✅ Source (`APPOINTMENT_SOURCE_LABELS`).
6. ✅ Language (`LANGUAGE_LABELS`).
7. ✅ Insurance captured — yes/no badge.
8. ✅ VOB status chip — `VobStatusChip abbreviated` (uses `VOB_CHIP_LABELS`, falls back for non-abbreviated); wrapped in a `Link` to the VOB record (`/vob-queue`). "none" when no VOB record.
9. ✅ Triage flag — `TriageChip`; red accents on High and Urgent come from the chip (`destructive`); sortable by severity.
10. ✅ Status — `AppointmentStatusChip`; sortable.
11. ✅ Booked by — agent name (`AGENT_LABELS`) + booked timestamp in location tz.
12. ✅ Location — only when multi-location.
- ✅ Paginated (12/page), prev/next, page indicator.
- ⚠️ Sorting/filtering are client-side. Spec §5.2 says "server-side"; there is no server in this build, so the same behavior is implemented against the fixture. Noted per instructions.

## §5.3 Filters
- ✅ Date range (from/to native date inputs, compared on the row's local date key), status, source, VOB status, triage flag, language, location (shown only when multi-location), free-text search on name + phone.
- ✅ Search audited in PHI mode: `recordPatientSearch(session, query)` called from the client, **debounced 400ms**; no-ops outside PHI mode and on empty input (enforced inside the frozen data-access function).

## §5.4 Detail drawer — all eight sub-items (Radix `Drawer`: focus trap, Escape, ARIA)
1. ✅ Full appointment record with unmask-on-demand phone (`MaskedValue`, same audited reveal).
2. ✅ Originating interaction link → `/conversations/calls?interaction={id}` (only when an originating interaction exists).
3. ✅ VOB card when a verification exists: payer, coverage status, copay, deductible, out-of-pocket, prior-auth flag, timestamp, and a link to the queue record. Sourced from `fixture.vobRecords` by `appointment.vobId`.
4. ✅ Confirmation and reminder history — each attempt with outcome via `CONFIRMATION_ATTEMPT_OUTCOME_LABELS`.
5. ✅ Timeline — each event with timestamp (location tz) and actor.
6. ✅ Outcome control — Mark completed / Mark no-show; calls `recordAppointmentStatusChange(session, id, from, to)`; gated on `canPerformWorkflowActions(session)` (Viewer sees a muted access note instead). Local optimistic status overlay feeds no-show analytics visibly.
7. ✅ Staff notes — append-only list + add form; calls `recordNoteEdit(session, `appointment:${id}`)`; gated on `canPerformWorkflowActions`. Existing notes render read-only for Viewer.
8. ⚠️ Flag this interaction — routes to Qualicall priority review (§12.5). Implemented as a **local optimistic mark + inline confirmation**, with **no audit event written**: "flag" is not among the twelve canonical §2.3 audit event types (the frozen `AuditEventType` has no `flag`), so writing one would neither compile nor be truthful. No new shared store invented; §12.5's inbox is another agent's surface. Narrowest correct interpretation.

Drawer state is local to the client component.

## §5.5 Calendar view (secondary toggle)
- ✅ Day and week **agenda** rendering of the same filtered/sorted data, toggled via `Tabs` (Table is primary).
- ✅ **No drag-to-reschedule** (rescheduling is an agent/EHR action, per spec).
- ⚠️ The agenda is forward-looking: it groups by each row's local date (§2.7) across a 1-day / 7-day window anchored at `MOCK_NOW`. Rows outside the window remain reachable in the primary table. Noted.

## §5.6 Empty and degraded states — all three
- ✅ No appointments yet → `EmptyState`. Verified against Cedar (`org_cedar`, `appointments: []`) which renders it.
- ⚠️ EHR sync unavailable → `Banner` (dismissible) stating outcomes are manual-entry until sync restores. Driven off `!org.outcomeDataAvailable` (Cedar = true → banner shows; Northside = false → hidden). This reuses the org's outcome-data flag as the sync signal, as instructed.
- ✅ NON-PHI mode → `listAppointments` returns `{ kind: 'aggregate', total, reason }`; the discriminated union forces the branch, so the table cannot render. Only aggregate counts + an explanatory banner show.

## Mode / role matrix (verified by construction against the data-access layer)
- ✅ PHI + Owner/Admin: full table, phone reveal, workflow actions, notes.
- ✅ PHI + Viewer: rows load; `phoneE164` omitted upstream so no reveal control; outcome controls and note form hidden (`canPerformWorkflowActions` false); no export control exists in this tab (exports are §16.1, not §5).
- ✅ NON-PHI (any role): aggregate counts only, table hidden.

## Traceability
Every UI element traces to a §5 bullet. No export button exists in this tab by design (§5 specifies none; exports live in §16.1). No status string or label is hardcoded — all come from `src/shared/status-models.ts`.
