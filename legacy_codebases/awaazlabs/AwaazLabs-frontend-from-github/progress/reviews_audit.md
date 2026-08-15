# §13 Review Taker & Reviews — self-audit

Bullet-by-bullet against spec §13.1 and §13.2. ✅ built · ⚠ interpretation/note · ❌ not built.

## Files (all inside owned route folders)

| File | Lines |
|---|---|
| `src/app/(dashboard)/agents/review-taker/page.tsx` | 10 |
| `src/app/(dashboard)/agents/review-taker/review-taker-client.tsx` | 175 |
| `src/app/(dashboard)/agents/review-taker/review-analytics.ts` | 184 |
| `src/app/(dashboard)/reviews/page.tsx` | 10 |
| `src/app/(dashboard)/reviews/reviews-client.tsx` | 270 |
| `src/app/(dashboard)/reviews/reviews-analytics.ts` | 173 |
| `src/app/(dashboard)/reviews/private-feedback-list.tsx` | 139 (shared by §13.1 and §13.2) |

Nothing outside these folders was modified.

---

## §13.1 — Review Taker (agent tab)

- ✅ **Renders through the §2.6 agent template** — `review-taker-client.tsx` composes `AgentAnalyticsPage` (stats, primaryChart, distribution, drillThrough, extra, emptyState). First tab in the repo to actually exercise the template, as §2.6's own doc-comment requires.
- ✅ **Eight-stage funnel** via the `Funnel` primitive. Stages, in order: completed appointments → eligible → called → reached → review ask delivered → agreed → link sent (SMS) → review posted (attributed). Computed by `reviewFunnel()` using a cumulative "reached at least stage k" ladder.
- ✅ **Per-stage count AND stage-to-stage conversion %** — count is the funnel's direct label; conversion % is rendered by the `Funnel` primitive between stages.
- ✅ **Single hue** — `Funnel` paints every stage `var(--chart-1)`; no ramp (THEME_NOTES §6).
- ✅ Stat: **Review calls placed · Patients reached · Reach rate** (`ratio(reached, callsPlaced)`).
- ✅ Stat: **Agreement rate** = agreed ÷ asks delivered (`ratio`).
- ✅ Stat: **Link-send rate** (sent ÷ agreed) and **Link-click rate** (clicked ÷ sent).
- ✅ Stat: **Reviews posted, attributed** — tooltip labels the attribution method (tracked link or Google Business Profile delta within the attribution window).
- ✅ Stat: **Average rating of attributed reviews** (`toFixed(1)`, `—` when none).
- ✅ Stat: **Opt-outs generated** — tooltip states each writes to the suppression list automatically.
- ✅ Stat: **Average call duration** (`formatDuration`, `—` when none).
- ✅ **Compliance note rendered in the UI** — prominent `Banner` (visible, not a tooltip/comment) with verbatim text; placed in the template's `extra` slot exactly as the template doc-comment prescribes. See verbatim text below.
- ✅ **No sentiment filter before the ask** — confirmed: the ladder/funnel has no sentiment branch; every eligible request proceeds to the ask, and `declined`/`opt_out` are mapped to the ask stage (index 3), i.e. they occur at/after the ask, never before it. No `sentiment`-keyed logic exists anywhere in scope.
- ✅ **Private feedback list** — `PrivateFeedbackList`, fed from `fixture.privateFeedback`, rendered in the `extra` slot.
- ✅ **Drill-through** to `/conversations/calls?agent=review_taker`.
- ⚠ **Distribution component** (`DistributionBar` of review-request outcomes: Posted / In pipeline / Declined / Opt-out). Required by the §2.6 template; expands the funnel's terminal population. Traceable to §2.6 + the §13.1 outcome bullets. Colors are documented palette tokens, no good/bad status token misused.

## Degraded / empty states (§13.1)

- ✅ **Cedar (`org_cedar`)** — `reviewRequests: []`, no appointments ⇒ `hasReviewActivity` false ⇒ template `emptyState` (`EmptyState`) renders. Funnel never divides by zero (`Funnel` clamps top to ≥1; all rates use `ratio()` → `null` → `—`).
- ✅ **NON-PHI** — funnel and stats are aggregate (review-request counts, no identity) and render normally. `PrivateFeedbackList` branches on `canSeePatientRows(session)`: withholds patient-level rows and the source-call link, showing an aggregate count only.

---

## §13.2 — Reviews (GROWTH tab, not the template)

- ✅ **Not an agent tab** — `reviews-client.tsx` renders directly, no `AgentAnalyticsPage`.
- ✅ **Rating trend chart** — `LineChart` of the cumulative Google rating over time, with **review-agent go-live via the `markers` prop** (`ratingTrend().goLiveIndex`, earliest review-agent call).
- ✅ **Reviews over time** — attributed vs organic **stacked** `BarChart` using `REVIEW_ATTRIBUTION_SERIES` from series-map.
- ✅ **Recent attributed reviews list** — date (location tz), rating, excerpt, and a **link to the live review** (`review.url`, external `target=_blank rel=noopener`).
- ✅ **Private feedback list** — date, patient, summary, **source call link** (`/conversations/calls?interaction=…`, which auto-opens that call's drawer), status (New / Actioned). Same shared component.
- ✅ **Location comparison table (multi-location only)** — rendered only when `isMultiLocation(org)`; per location: rating, attributed reviews this month, agreement rate.
- ✅ **Scope boundary respected** — built **no** review responding, **no** listings management, **no** social publishing. The only occurrences of those words in scope are the comments stating they are deliberately absent (grep check 4).

## Degraded / empty states (§13.2)

- ✅ **Cedar** — no published reviews / review requests ⇒ `hasReviewsData` false ⇒ full-tab `EmptyState`. Sub-lists also have their own empty states. No divide-by-zero (`ratio()` throughout).
- ✅ **NON-PHI** — ratings, review counts and location comparison are public/aggregate and render; only `PrivateFeedbackList` withholds patient rows + source-call link.

---

## Compliance note — verbatim text as rendered (a prominent `Banner`)

> **Compliance note (rendered in the UI and enforced in the pipeline)**
> Every eligible patient receives the ask; no sentiment pre-filtering before the ask (review gating violates Google policy). Patients expressing a negative experience are routed to a private feedback capture after the ask, not instead of it.

---

## The 8 funnel stages, in order

1. Completed appointments
2. Eligible
3. Called
4. Reached
5. Review ask delivered
6. Agreed
7. Link sent (SMS)
8. Review posted (attributed)

## Mechanical checks

- `npx tsc --noEmit` → 0 errors.
- `npx eslint` on both folders → clean.
- literal-color grep → empty.
- `: any` / `as any` grep → empty.
- forbidden-scope grep → only the compliance note + scope-boundary comments (all asserting absence).

No UI element in scope lacks a traceable spec bullet (the one template-mandated distribution component is traced to §2.6 in combination with §13.1).
