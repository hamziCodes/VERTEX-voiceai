# Mock Fixtures — Coverage Audit

> ## ⚠ READ THE ERRATA AT THE BOTTOM FIRST
>
> The row counts and figures in the body of this document were written **before** a defect
> pass and are **stale**. Every check below passed while the Overview tab would have
> rendered a 288% booking rate — a referential-integrity script verifies that ids resolve;
> it cannot catch a distribution defect. Corrected, re-verified figures are in the
> **Errata** section at the end of this file.


Files: `src/mock/fixtures/{helpers,northside,cedar,index}.ts`. All timestamps derive from
`MOCK_NOW_UTC` (`2026-07-09T15:20:00.000Z`); no wall-clock reads, no platform RNG (seeded
mulberry32 only). `npx tsc --noEmit` is clean; forbidden-token greps
(`Math.random`/`Date.now()`, `dob|ssn|diagnosis|clinicalNote`) return nothing.

Coverage legend per guide Part D item 5: **normal** row, **empty** state, **needs-attention / aging** state.

| Domain | Northside (demo) | Cedar (sparse) | Normal | Empty | Needs-attn / aging | Status |
|---|---|---|---|---|---|---|
| contacts | 60 (en/es/other, some suppressed, some `insurance:null`) | 8 | ✅ | Cedar 8 (small) | suppressed contacts | ✅ |
| appointments | 120, all 6 statuses, all 4 sources, 18 after-hours, 7 recovered no-shows | **0 (empty state §5.6)** | ✅ | ✅ Cedar | no_show / cancelled rows | ✅ |
| vobRecords | 45, all 12 statuses, 6 payers w/ variance | 3 (incl `unable_to_verify`) | ✅ | — | 4 red + 5 amber aging, 3 fresh queued | ✅ |
| calls | 147, 5 voice agents, all 10 dispositions, grade-lift baked in | 6 | ✅ | — | escalated / no-answer / abandoned | ✅ |
| chats | 70, both channels, all 4 outcomes, handoff markers | 4 | ✅ | — | escalated w/ human handoff | ✅ |
| escalations | 18, all 5 triggers, 6 open past ack threshold | **0 (empty state)** | ✅ | ✅ Cedar | 6 open past threshold → banner | ✅ |
| optimizationEvents | 10, all 4 statuses, 1 full receptionist cycle w/ +11 delta | 0 | ✅ | ✅ Cedar | in_tuning / detected pending | ✅ |
| flags | 8, all 3 statuses | 0 | ✅ | ✅ Cedar | submitted / under_review | ✅ |
| reviewRequests | 19, 8-stage funnel incl `declined` + `opt_out` | **0 (no appts to ref)** | ✅ | ✅ Cedar | declined / opt_out drop-off | ✅ |
| privateFeedback | 4 (new + actioned) | 0 | ✅ | ✅ Cedar | new (unactioned) | ✅ |
| publishedReviews | 14 (8 attributed / 6 organic) | 0 | ✅ | ✅ Cedar | — | ✅ |
| campaigns | 3 (running/paused/completed), all 6 contact statuses each | **0 (empty state)** | ✅ | ✅ Cedar | exhausted / opt_out contacts | ✅ |
| knowledgeBlocks | all 8 categories | 3 | ✅ | — | — | ✅ |
| knowledgeRequests | 4, all 4 statuses w/ history | 0 | ✅ | ✅ Cedar | requested / in_review | ✅ |
| members | 5, all 3 roles, mixed MFA | 2 | ✅ | — | MFA-disabled members | ✅ |
| lines | 6, ≥1 `healthy:false` | 2 | ✅ | — | 1 unhealthy → banner | ✅ |
| suppressionList | 12, all 3 sources | 2 | ✅ | — | complaint entries | ✅ |
| invoices | 6 (1 due / 5 paid) | 2 | ✅ | — | due invoice | ✅ |
| agents | 7 = 6 standard + 1 custom (`post_op_followup`) | 6 standard | ✅ | — | custom agent | ✅ |
| usage meters | 10,920 / 12,000 min = 91% (banner) | 610 / 2,500 | ✅ | — | 90%+ usage → banner | ✅ |

## Org-level degradation states (Cedar)
- Single location → §2.4 location filter hides. ✅
- `avgAppointmentValueUsd: null` → §4.3 revenue card hides. ✅
- `outcomeDataAvailable: false` → §4.1 no-show card hides (no misleading zero). ✅

## Cross-tab consistency verified by `audit.cjs`
- appointment ↔ VOB links bidirectional; call/chat `linked.*` bidirectional. ✅
- reengagement revenue reproducible: 4 reengagement bookings × $285, all mapped to real appts;
  after-hours bookings=18, recovered no-shows=7 (feed §4.3). ✅
- Seeded optimization cycle: `opt_ns_001` (receptionist) detected→in_tuning→deployed→verified,
  gradeDelta +11; receptionist call grades before deploy avg 82.1 → after 91.7. ✅

## Known interpretations
- N1: Calls use the five **voice** agents per §10.1; the `chat` AgentId is exercised via chats
  (a call with agent `chat` would contradict §10.1). Every AgentId is represented across the
  interaction set. See BUILD_NOTES B2 for the `verifier` agent.
- N2: Only booking calls (and reengagement-booked calls) set `linked.appointmentId`
  (= "appointment created", §10.1); confirmation calls relate to an appointment but did not
  create it, keeping the appointment ↔ originating-interaction link exactly bidirectional.
- Northside calls total 147 (~150): verifier calls track the 22 `confirmed` appointments rather
  than a fixed 25, so the count follows the appointment data rather than padding it.

---

## ERRATA — figures above superseded after the time-skew repair

The counts in the sections above were written before a defect pass. They are **stale**.
Phase 3 must read the corrected figures below, verified by running the real
`src/lib/metrics.ts` against the fixtures (not by re-deriving them).

**Why the repair was needed.** The original integrity script counted every domain across
*all time*. The spec scopes several cards to `today`, `this week`, and `this month`
(`MOCK_NOW_UTC = 2026-07-09T15:20:00Z`, so "this month" is only Jul 1–9). Every check
passed while the Overview tab would have rendered a **288% booking rate** — bookings were
clustered into the trailing 7 days while interactions spread across 45. A referential
integrity check cannot catch a distribution defect.

| Field | Stale value | Corrected |
|---|---|---|
| Total calls | 147 | **181** |
| Booking rate (this week) | 288.2% ❌ | **67.3%** ✅ |
| Booked today vs same weekday last week | 10 vs 1 | **11 vs 10** |
| Recovered no-shows (this month, §4.3) | 0 | **4** |
| Revenue recovered estimate | $3,705 | **$4,845** |
| VOB completed today | 0 | **3** |
| Quality trend (30d) | started at 0 (empty leading bucket) | **82 → 91** |

Unchanged and re-verified: aggregate quality score **89**; 4 red / 5 amber aging VOB rows;
all 12 VOB statuses, all 10 call dispositions, all 6 appointment statuses; 6 payers with
materially different verified rates; consent disclosure set iff `loc_north`; usage 91% of
plan; ≥1 unhealthy line; 6 open escalations past threshold; appointments still 120.

All four §4.6 attention-banner conditions fire: `escalation_aging`, `vob_aging`,
`line_health`, `usage_threshold`.

No future-dated calls or bookings. Cedar's degraded paths verified: revenue card hides,
banner empty, appointments empty.
