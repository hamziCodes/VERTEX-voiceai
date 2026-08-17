# §11 Escalations tab — Part D self-audit

Bullet-by-bullet against spec §11.1–§11.3. ✅ met · ⚠ met with a noted interpretation · ❌ not met.

Files (all under `src/app/(dashboard)/escalations/`):
`page.tsx`, `escalations-client.tsx`, `escalations-table.tsx`, `escalations-stat-strip.tsx`,
`escalations-filters.tsx`, `escalation-detail-drawer.tsx`, `escalation-metrics.ts`, `types.ts`.

Every UI element traces to a §11 line; no element exists that cannot be pointed at a spec bullet.

## §11 purpose
- ✅ "Every safety escalation and clinical-question routing in one accountable surface." — one table + acknowledgement workflow + stat strip.

## §11.1 Table columns
Nine columns, in order. Eight trace to §11.1; the **Aging** column is the §11.2 aging indicator.
1. ✅ **Timestamp** — `formatDateTime` in the location timezone (§2.7 via `lib/format`), never `toLocaleString()`.
2. ✅ **Patient name** — resolved from `fixture.contacts[contactId].identity`; rendered only in PHI mode (see NON-PHI branch).
3. ✅ **Source interaction (call or chat, link)** — `/conversations/calls?interaction={id}` or `/conversations/chats?interaction={id}`, resolved by membership in `fixture.calls` ids.
4. ✅ **Trigger** — `ESCALATION_TRIGGER_LABELS` (Triage High, Urgent or Emergency, Clinical question, Caller requested human, Agent-initiated). No literal.
5. ✅ **Routed to** — `record.routedTo` (staff member or forwarding number, from the fixture).
6. ✅ **Acknowledged (yes/no with timestamp)** — "Yes · {ack time} · {by}" or, when `canAck`, the one-tap Acknowledge button; a Viewer sees read-only "No".
7. ✅ **Aging (§11.2)** — `AgingBadge` on rows open past their threshold; "—" otherwise.
8. ✅ **Resolution note** — the note text, or an "Add note" affordance when `canAck`.
9. ✅ **Location** — `getLocationById(...).name`.

## §11.2 Acknowledgement workflow
- ✅ "Escalations arrive unacknowledged" — fixture seeds `status: 'open'` rows with `acknowledgedAtUtc: null`.
- ✅ "Any Manager or Owner can acknowledge" — gated on `canAcknowledgeEscalation(session)` (role ≠ VIEWER). A Viewer sees no acknowledge control anywhere (table or drawer).
- ✅ "one tap" — inline Acknowledge button in the Acknowledged column; a single press acknowledges.
- ⚠ "audited" — **no `escalation_acknowledged` type exists** in §2.3's twelve. Per the task instruction and BUILD_NOTES B14's precedent, **no thirteenth type is invented**:
  - the bare acknowledgement tap writes **no** audit event (there is no truthful existing type for a pure acknowledgement);
  - **appending an outcome note** writes the existing, truthful `note_edit` event via `recordNoteEdit`.
  This is the honest reading of "audited" against a frozen, closed audit union.
- ✅ "append an outcome note" — drawer textarea → `recordNoteEdit(session, 'escalation:{id}')` → optimistic `resolutionNote`. `recordNoteEdit` refuses structurally for a Viewer.
- ✅ "updates local optimistic state (fixture read-only), records actor + timestamp" — `overrides` state stores `acknowledgedAtUtc = mockNow()` and `acknowledgedBy = session.actor`.
- ✅ "unacknowledged older than threshold (30 min Urgent, 4 hr otherwise) → Overview banner" — `isPastThreshold` reuses the exact rule from `attentionConditions` and reads `ESCALATION_ACK_THRESHOLD_MINUTES` (never hardcodes 30/240). The banner itself already works and is untouched.
- ✅ aging indicator via `AgingBadge` — always icon + text (amber is 1.83:1); not stripped. Fires on exactly the 6 seeded open-past-threshold rows (the 7th open row, `caller_requested_human` at 90 min < 240, correctly does **not** fire).

## §11.3 Stat strip
- ✅ **Escalations this week** — `StatCard`, `isThisWeek(atUtc)`.
- ⚠ **Acknowledgement rate** — `StatCard`; acknowledged (has `acknowledgedAtUtc`, i.e. acknowledged or resolved) ÷ total, over the location-scoped set (not filtered by the table's status/trigger filters). Window ambiguity resolved to the scoped overview; stated in a tooltip. Null-safe → "—".
- ⚠ **Median time to acknowledge** — `StatCard`; median of (ack − arrival) across acknowledged escalations, rendered via `formatDuration`. Same scope note; null-safe → "—".
- ✅ **Breakdown by trigger** — `DistributionBar` (through `ChartFrame`), with a `tableData` relief table built from the *same* per-trigger counts the bar plots. Trigger→color binding centralized in `types.ts` (`TRIGGER_SERIES`, categorical `--chart-*`) because the canonical `series-map.ts` is frozen and carries no trigger binding.

## Degraded / empty states
- ✅ **NON-PHI** — branch on `canSeePatientRows(session)` (§10.4 precedent): render aggregate count + stat strip, hide the patient table.
- ✅ **Viewer** — `canAck` false → no acknowledge/note controls; read-only table + stat strip.
- ✅ **Cedar (`org_cedar`, escalations: [])** — `scoped.length === 0` → `EmptyState`, no crash.

## Mechanical checks
- `npx tsc --noEmit`: zero errors in scope (only unrelated error is `agents/review-taker`, another agent's frozen folder).
- `npx eslint src/app/(dashboard)/escalations`: clean.
- no literal colors, no `any`/`as any` in scope.
- `\b30\b|\b240\b|\b4 hours\b`: one hit — a spec-quote comment in `escalation-metrics.ts`; the value is read from `ESCALATION_ACK_THRESHOLD_MINUTES`, never inlined.
