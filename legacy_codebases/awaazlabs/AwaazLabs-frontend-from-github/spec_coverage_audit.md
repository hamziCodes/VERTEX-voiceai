# spec_coverage_audit.md

**Phase 3 deliverable** (guide Part H). Every section of `qualicall_dashboard_spec.md`,
walked in order, re-verified against the merged codebase — not merely copied from the
batch self-reports in `progress/*_audit.md`.

## Legend

| Mark | Meaning |
|---|---|
| ✅ | Built, matches the spec bullet exactly |
| ⚠️ | Built but diverges — divergence explained and logged in `BUILD_NOTES.md` |
| 🔜 | **Milestone 2.** Not built. Renders a real Under Construction page in the correct nav slot |
| ❌ | Missing, and not scheduled — escalated explicitly |

**Milestone 1 scope** was set by the CTO as the spec's own §19 "demo spine" (build-priority
items 1–6), which §19 calls non-negotiable. Everything outside it is 🔜 by design, not by
omission. A 🔜 is not a failure; a ❌ is.

---

## §1 — Product context

Narrative. §1.4's agent catalog is realised as the agent registry (§2.6); §1.5's loop is
Section 12. No UI surface of its own.

---

## §2 — Global architecture

| Bullet | Status | Evidence |
|---|---|---|
| 2.1 NON-PHI vs PHI mode; mode badge on every page header | ✅ | `TopBar.tsx` badge; `data-access.ts` returns a discriminated `aggregate` arm in NON-PHI so rows are structurally unrepresentable |
| 2.1 NON-PHI degradation on Appointments, VOB Queue, Conversations | ✅ | Verified by execution: `listAppointments`/`listCalls`/`listVobRecords` all return `{ kind: 'aggregate' }` |
| 2.1 NON-PHI degradation on Audit Log | 🔜 | Audit Log tab is §16.2, Milestone 2. The **gate** is live: `canSeeAuditLog` requires PHI + Owner, and `RouteGuard` rejects the URL |
| 2.2 Three roles: Owner/Admin, Manager, Viewer | ✅ | `ROLES` in `status-models.ts`; one `OWNER_ADMIN` role, per BUILD_NOTES B7 |
| 2.2 "UI hides what the role cannot access; the API independently rejects it" | ✅ | Both halves built. Nav hides (`visibleNavGroups`); `RouteGuard` rejects the typed URL; `data-access.ts` omits the field. Executed: a Viewer's rows carry `phoneE164: null`, `media: null`; `revealPhone()` and `recordExport()` throw `PermissionDeniedError` |
| 2.3 Twelve audited event types | ✅ | `audit.ts` — exactly 12, machine-counted. No thirteenth added for flagging (BUILD_NOTES B14) |
| 2.3 Writes happen at the action layer and cannot be disabled | ✅ | No `disableAudit` switch exists. Executed: 3 gated actions → 3 audit rows; export row carries `rowCount` and filter params per §16.1 |
| 2.3 Audit Log is the read surface | 🔜 | Store is live and populated; the §16.2 **tab** is Milestone 2 |
| 2.4 Org > Location > Agent; every row carries `location_id` | ✅ | Enforced in `schema.ts`; verified by the fixture integrity script |
| 2.4 Global location filter in the top bar, persists across tabs | ✅ | `SessionProvider` holds it; every metric applies `scopeToLocation`. **Persists across a hard reload too** (`localStorage`, validated on read) — client-side nav alone satisfied the letter but not the intent. BUILD_NOTES B19 |
| 2.4 Single-location clinics see no filter | ✅ | `showLocationFilter = isMultiLocation(org)`. Cedar (1 location) exercises it |
| 2.5 Patient envelope limited to the listed fields | ✅ | `schema.ts` |
| 2.5 No DOB, SSN, clinical notes, diagnosis — *structurally impossible* | ✅ | `NoPhi<T>` resolves to a poison type if any forbidden key is declared. Adding `dob: string` fails `tsc`, not lint |
| 2.6 Agent registry: name, type, channel, icon, metrics contract | ✅ | `AgentRegistryEntry`; 6 standard + 1 custom (`post_op_followup`) seeded |
| 2.6 Custom agents append to the AGENTS nav from the registry | ✅ | `DashboardShell` appends them; `/agents/[slug]` route exists |
| 2.6 Standard agent analytics page template | 🔜 | The template page is Milestone 2. The registry, nav slot, and route are live |
| 2.7 UTC storage, render in the location's timezone | ✅ | `format.ts`; `timezoneFor(orgId, locationId)`. A bare `toLocaleString()` anywhere is a defect |
| 2.7 Patient interaction language as a data dimension | ✅ | `language` on every contact; drives §6.2/§9.2 language-mix charts (those tabs 🔜). Deliberately a **different type** from the UI locale |
| 2.7 **i18n framework in place day one** | ✅ | `src/i18n/`. Zero new dependencies. `es.ts` is typed `Record<MessageKey, string>`, so a key without a Spanish translation is a **compile error** — no silent English fallback. Locale persists across reloads and updates `<html lang>`. Verified in a browser: nav, top bar, and placeholder states translate; `<html lang>` becomes `es-US` |
| 2.7 "UI ships English" | ✅ | `DEFAULT_LOCALE = 'en'`. Chrome is translated; page bodies ship English, exactly as the sentence states |
| 2.8 HIPAA: BAA-gated PHI mode, audit log, RBAC | ✅ | Mode gate, audit writer, role gate all live |
| 2.8 TCPA/DNC suppression list, consent basis | 🔜 | Data model live (`suppressed`, `consentBasis`, `SuppressionEntry`); the §16.5 settings surface is Milestone 2 |
| 2.8 Call recording consent: per-location one/two-party; disclosure stored on the record | ✅ | `recordingConsentMode` per location; `media.consentDisclosureAtUtc` set **iff** the call is at `loc_north` (two-party). Rendered in the §10.1 drawer. Verified by the fixture script |
| 2.8 Review solicitation: no sentiment pre-filter before the ask | 🔜 | §13.1 is Milestone 2. The architecture does not implement a sentiment filter, and the review-request enum has no gate state |

---

## §3 — Navigation architecture

| Bullet | Status | Evidence |
|---|---|---|
| Top bar: org switcher, location filter, mode badge, notifications bell, user menu | ✅ | Exactly those five in `TopBar.tsx`. Nothing else |
| Left nav tree, exactly as specified | ✅ | `nav.ts`. **23 nav routes, all resolve — 0 broken links (machine-checked)** |
| COMPLIANCE group is PHI-mode only | ✅ | `visibleWhen: canSeeAuditLog` (PHI + Owner, per §16.2's narrower rule) |
| Custom agents append under AGENTS | ✅ | From the registry |
| Ten non-spec nav items deleted | ✅ | All 9 removed routes confirmed absent; **0 stale references** in `src/` |
| Group order is a product decision, not sorted | ✅ | `NAV_GROUPS` is an ordered literal with the rule quoted in-file |
| Demo controls (role/mode switchers) not in the top bar | ⚠️ | §3's top bar has a mode *badge*, not a switcher; the guide (F.3) requires both togglable. Toggles live in the user menu under a visible "Demo controls" heading. BUILD_NOTES A9 |

**Unlisted extras:** two routes exist outside the nav — `/conversations` (a redirect to
`/conversations/calls`, since §3 lists sub-views but no index) and `/agents/[slug]` (the
§2.6 registry slot). Both traceable. No other extras.

---

## §4 — Overview  ✅ COMPLETE

| Bullet | Status |
|---|---|
| 4.1 A: 4 stat cards (booked today + weekday delta; booked this week + booking rate; upcoming 7d; no-shows/cancellations + rate) | ✅ |
| 4.1 No-show card **hides** rather than showing a misleading zero when outcome data is unavailable | ✅ Executed on Cedar (`outcomeDataAvailable: false`) |
| 4.1 Bookings over time, 7D/30D toggle, stacked by source (Voice/WhatsApp/Web Chat) | ✅ |
| 4.2 B: 3 cards (in progress + sub-statuses; completed today/week + verified rate; needs attention, red accent, click-through pre-filtered) | ✅ `?filter=needs-attention` honoured by VOB Queue |
| 4.2 Compact horizontal status distribution bar mirroring the VOB tab | ⚠️ Three color-safe groups, per-status detail in the relief table. BUILD_NOTES B15 |
| 4.3 C: revenue estimate = (after-hours + reengagement + recovered no-shows) × avg value | ✅ Executed: `$4,845 == 17 × $285` |
| 4.3 Card **hides** if avg value unset; tooltip shows formula and inputs | ✅ Executed: returns `null` on Cedar |
| 4.4 D: aggregate grade, 30-day sparkline, optimization-event count, click-through | ✅ Score **89**, identical to §12.2 — same function, not two derivations |
| 4.5 E: interactions row per-agent + Overall + All | ⚠️ "Overall"/"All" undefined in spec; Overall = voice, All = all channels. Documented in-UI |
| 4.5 Calls/minutes today, avg duration, avg cost per interaction | ✅ |
| 4.5 Calls over time AND minutes over time (7D/30D) | ✅ **Two separate charts.** Never dual-axis |
| 4.5 Avg first-audio response with 800 ms target line | ✅ Reads `FIRST_AUDIO_TARGET_MS`, not a magic number |
| 4.5 Success rate with completion counts; live calls now with refresh timestamp | ✅ |
| 4.6 F: dismissible red banner, four documented triggers, each deep-linking | ✅ **All four fire** on the demo org; all four deep-links resolve |

---

## §5 — Appointments  ✅ COMPLETE

| Bullet | Status |
|---|---|
| 5.1 Header stats strip (4 metrics) | ✅ from `appointmentStats` |
| 5.2 Table columns | ✅ **12 columns exactly**, as the spec enumerates. The guide's "13" is a miscount — BUILD_NOTES B4 |
| 5.2 Phone masked, click-to-reveal, reveal audited | ✅ A Viewer receives no raw number, so no reveal control renders |
| 5.2 VOB status chip using the canonical model, links to the VOB record | ✅ |
| 5.2 Red accents on triage High and Urgent | ✅ |
| 5.3 Filters incl. free-text search, audited in PHI mode | ✅ `recordPatientSearch`, debounced; records query *length*, never the query |
| 5.4 Detail drawer — all 8 sub-items | ✅ 8/8 |
| 5.5 Calendar view, day/week, **no drag-to-reschedule** | ✅ |
| 5.6 Empty state / EHR-sync banner / NON-PHI aggregate-only | ✅ All three. ⚠️ EHR-sync banner is driven off `!outcomeDataAvailable` — the fixture has no dedicated sync flag |
| Server-side filtering and sorting | ⚠️ No server exists (hardcoded-data build). Same behavior implemented client-side |

---

## §6 — Receptionist  🔜 Milestone 2

---

## §7 — VOB Agent  ✅ COMPLETE

| Bullet | Status |
|---|---|
| 7.1 All stat cards, incl. each terminal status as % with count on hover | ✅ |
| 7.1 Benefit-capture completeness decomposed into 3 sub-bars | ✅ copay / deductible / OOP-max |
| 7.1 Avg handle time **and** turnaround time (median **and** P95) | ✅ All four rendered, labelled distinctly |
| 7.2 VOB status distribution bars summing to 100% | ⚠️ Three color-safe groups; per-status counts in the relief table. BUILD_NOTES B15 |
| 7.2 Verifications over time | ✅ |
| 7.2 Payer breakdown table, **visually prominent** | ✅ Full-width, sorted by unable-to-verify rate **descending** so problem payers surface first. 6 payers with materially different rates (0%–71% verified) |
| 7.3 Canonical status model shared across 4 surfaces | ✅ 12 statuses, one `VOB_STATUS_LABELS` map, machine-verified |

---

## §8 — VOB Queue  ✅ COMPLETE

| Bullet | Status |
|---|---|
| 8.1 Worklist table, 10 columns | ✅ |
| 8.1 Aging: amber past 24h non-terminal, red past 48h | ✅ Imports `VOB_AGING_THRESHOLD_HOURS`. Fixture seeds 4 red / 5 amber. Amber (1.83:1) always ships icon + text |
| 8.2 Row drawer: benefits, prior-auth/referral flags, per-attempt call log with recordings + transcripts, payer reference numbers | ✅ |
| 8.3 Four row actions, each writing an audit event and updating the status timeline | ✅ Retry / Mark resolved (reason picker) / Escalate / Add note |
| 8.3 "Mark resolved" | ⚠️ §17 has no `resolved` VOB status. Records the reason, appends a timeline entry, drops the row from the exception worklist. No status invented. BUILD_NOTES B16 |
| 8.4 Filters, bulk retry, audited CSV export (role-gated) | ✅ Export reads only the projected `ContactView`; **an unrevealed phone exports as its mask** |
| Flag button | ⚠️ Not in §8.3's four actions, but §12.5 names VOB Queue as a flag source. Traceable to §12.5. BUILD_NOTES B17 |

---

## §9 — Chat Agents  🔜 Milestone 2

---

## §10 — Conversations  ✅ COMPLETE

| Bullet | Status |
|---|---|
| 10.1 Calls table, 10 columns | ✅ |
| 10.1 Drawer: audio player (role-gated, playback audited) | ✅ Viewer receives `media: null` → no player exists to disable |
| 10.1 Full transcript with speaker labels and PII redaction markers | ✅ Rendered via `String.slice()` into React text nodes. **No `dangerouslySetInnerHTML` anywhere in `src/`** |
| 10.1 Recording-consent disclosure event when two-party mode active | ✅ Renders **iff** the call is at `loc_north` |
| 10.1 QA grade breakdown (§12.3) inline | ✅ Imports `GradeBreakdown` from the Quality tab — not duplicated |
| 10.1 Linked objects: appointment, VOB, review request, campaign | ✅ |
| 10.1 Flag this interaction | ✅ Writes to `flag-store` → §12.5 inbox |
| 10.2 Chats: thread list + thread detail with handoff markers | ✅ |
| 10.3 Shared filter bar across both sub-views, search audited | ✅ State lifted; persists across the tab switch |
| 10.4 NON-PHI: aggregate counts only, no rows/recordings/transcripts | ✅ Executed |

---

## §11 — Escalations  🔜 Milestone 2

The §11.2 **thresholds are already live**: `ESCALATION_ACK_THRESHOLD_MINUTES` (30 min Urgent
/ 4 hr otherwise) drives the §4.6 Overview attention banner and the notifications bell,
both verified firing. Only the tab itself is deferred.

---

## §12 — Quality and Optimization  ✅ COMPLETE (the centerpiece)

| Bullet | Status |
|---|---|
| 12.1 Four-stage loop graphic, live counts, per-stage click-through | ✅ Each stage filters the page below |
| 12.2 Current quality score | ✅ **89**, identical to Overview's — one function, imported twice |
| 12.2 30-day **and** 90-day trend with optimization events plotted as markers | ✅ |
| 12.2 Grade distribution histogram | ✅ Bands `<70 · 70–79 · 80–84 · 85–89 · 90–94 · 95–100` |
| 12.2 Per-agent quality table with trend arrow and open items | ✅ |
| 12.3 All five grading dimensions, per-call and aggregate | ✅ Exported as `GradeBreakdown`, consumed by §10.1 |
| 12.4 Optimization timeline: date, agent, detected, changed, status, grade delta | ✅ Signed delta rendered |
| 12.4 **Internal tuning mechanics never exposed** | ✅ Grep-verified: no prompt, model name, temperature, or reviewer identity is user-visible |
| 12.5 Flagged interactions inbox, fed by real actions from three surfaces | ✅ `flag-store`, not a static fixture. Executed |
| 12.6 Exactly three compliance rates | ✅ Clinical boundary adherence (from grading dimension two), disclosure delivery, escalation correctness |
| §19 final line: seed one full `detected → verified` cycle with a visible grade lift | ✅ **Executed.** Receptionist grades: **82.15 before** the deployment marker, **91.62 after**. The lift is in the call data, not merely declared in a field |

---

## §13, §14, §15  🔜 Milestone 2

Review Taker + Reviews; Reengagement + Campaigns; Agent Knowledge.
Fixtures for all three exist and pass integrity checks, so these surfaces have real data
waiting.

---

## §16 — Remaining tabs  🔜 Milestone 2

All eight sub-tabs. Two notes:
- **§16.2 Audit Log** — the store it will read is live and populated by every gated action
  across the app today. The tab is a stub, but its data source is real, satisfying the
  guide's Rule 7 requirement that it "must be fed by real actions elsewhere in the app."
- **§16.3/§16.4/§16.2** are role-gated *now*, not later: `RouteGuard` rejects a Viewer or
  Manager who types the URL.

---

## §17 — Canonical status models  ✅ COMPLETE

All eight models implemented verbatim in `src/shared/status-models.ts`, declared exactly
once.

**Rule 5 grep result:** two hits outside that file, both **typed subsets, not
redeclarations** —
`SHARE_STATUSES ... satisfies readonly VobTerminalStatus[]` (§7.1's six hover-percentage
statuses) and `new Set<CallDisposition>([...])` in the fixtures. Both are constrained by the
canonical union, so an invalid member fails to compile. Not defects.

---

## §18 — Competitive position

Narrative. §18's claim that "no competitor surfaces a per-call grading and optimization loop
to the client" is realised by §12, which is built.

---

## §19 — Build priority order

**Items 1–6 are the demo spine and are explicitly non-negotiable.** All six are ✅:

| # | Item | Status |
|---|---|---|
| 1 | Global frame: navigation, mode badge, roles, location filter (2.1–2.4) | ✅ |
| 2 | Overview restructure, all six sections (§4) | ✅ |
| 3 | Appointments: table, filters, drawer, manual outcome control (§5) | ✅ |
| 4 | Canonical enums (§17) wired into VOB tab + VOB Queue with row actions (§7, §8) | ✅ |
| 5 | Conversations: calls with recording/transcript/grade badge; chats (§10) | ✅ |
| 6 | Quality and Optimization: loop, trend with markers, timeline, flag inbox (§12) | ✅ |
| 7–11 | Reviews, Campaigns, Escalations, Knowledge, Settings, Reports, Audit Log | 🔜 Milestone 2 |

§19: "Anything cut under time pressure comes from the bottom of this list, never the top."
The cut line falls exactly between item 6 and item 7.

---

## Verification method

Nothing in this document is copied from a batch self-report without re-checking. The
following were **executed**, not inspected:

```
Overview quality pulse == Quality tab score .......... PASS (89)
Revenue estimate == units × configured avg value ..... PASS ($4,845 == 17 × $285)
Revenue card hides when avg value unset ............. PASS (null on Cedar)
VOB status: one canonical 12-entry label map ........ PASS
Flag button → §12.5 inbox ........................... PASS (store, status `submitted`)
3 gated actions → 3 audit rows ...................... PASS
Export audit row carries rowCount + filters ......... PASS
Viewer: phoneE164 absent from every row ............. PASS
Viewer: media (recording+transcript) omitted ........ PASS
Viewer: revealPhone() throws PermissionDenied ....... PASS
Viewer: recordExport() throws PermissionDenied ...... PASS
NON-PHI: appointments/calls return aggregate arm .... PASS
23 nav routes resolve, 0 broken links ............... PASS
4 attention-banner deep-links resolve ............... PASS
9 Phase-0 REMOVE routes absent, 0 stale refs ........ PASS
Literal colors anywhere in src/ ..................... PASS (none)
`any` / `dangerouslySetInnerHTML` anywhere in src/ .. PASS (none)
Audit event types == 12 ............................. PASS
npx tsc --noEmit .................................... exit 0
npx next build (lint + types) ....................... 26 routes, green
```

## Open items — never silently shipped

Two items from the first pass have since been **resolved**:

| # | Item | Status |
|---|---|---|
| ~~1~~ | §2.7 UI-locale i18n framework | ✅ **BUILT.** `src/i18n/`. See BUILD_NOTES B6 |
| ~~2~~ | 2 moderate `npm audit` findings | ✅ **FIXED.** An `overrides` block forces `postcss@8.5.16`; `npm audit` now reports **0 vulnerabilities**. My earlier "unfixable" analysis was wrong and is corrected in BUILD_NOTES A12 |

Remaining:

| # | Item | Why |
|---|---|---|
| 1 | Dark mode | ❌ Deferred by explicit CTO decision. The spec never mentions it and no §-numbered screen requires it. A dark palette must be *selected and re-validated* against a dark surface, never flipped. BUILD_NOTES A8 / D3 |
| 2 | Server-side sort/filter (§5.2) | ⚠ Not implementable: this build has no server, by design (guide Rule 4, "Data is hardcoded only"). Behavior is identical, client-side. `data-access.ts` is the seam a real API replaces |

**No ❌ exists inside the Milestone 1 scope.** Every Milestone-1 bullet is ✅ or a
documented ⚠️.

---

## Post-audit defect pass

Four defects were found *after* the first Phase 3 pass, all by exercising the running
application rather than reading it. Recorded because the method matters more than the
individual bugs:

| Defect | How it was found | Why static checks missed it |
|---|---|---|
| VOB "Needs attention" segment painted **black** | Screenshot of the rendered page | `--destructive` is an HSL *triple*; `fill="var(--destructive)"` yields an invalid color and SVG falls back to black **without erroring**. `tsc`, ESLint, and the no-literal-color grep all pass |
| "Average cost per interaction" rendered **$0** | Screenshot | `formatUsd` rounds to whole dollars — correct for the $4,845 revenue card, catastrophic for $0.205 |
| Table rows were `role="button"` **containing** reveal buttons | Browser a11y probe | Valid TypeScript, valid JSX. Invalid ARIA: interactive control nested inside an interactive control. BUILD_NOTES B18 |
| Locale reset on hard page load | Browser probe after switching to Spanish | Client state with no persistence. A locale switcher that forgets is not a framework |

A guard now exists for the first: an automated sweep enumerates every HSL-triple token in
`globals.css` and asserts each occurrence in `src/` is wrapped in `hsl()`.
