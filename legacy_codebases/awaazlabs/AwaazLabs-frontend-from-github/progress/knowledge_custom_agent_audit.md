# Self-audit — §15 Agent Knowledge & §2.6 Custom-agent route

Purpose (§15, quoted): "answers the clinic owner's biggest trust question: **what is this
system telling my patients.** Read-only with a controlled change workflow."

Legend: ✅ built & verified · ⚠ built with a noted interpretation · ❌ not done

## Files (owned scope only)

| File | Lines |
|---|---|
| `src/app/(dashboard)/knowledge/page.tsx` | 9 |
| `src/app/(dashboard)/knowledge/knowledge-client.tsx` | 228 |
| `src/app/(dashboard)/knowledge/change-request-form.tsx` | 190 |
| `src/app/(dashboard)/knowledge/categories.ts` | 22 |
| `src/app/(dashboard)/agents/[slug]/page.tsx` | 17 |
| `src/app/(dashboard)/agents/[slug]/custom-agent-client.tsx` | 143 |
| `src/app/(dashboard)/agents/[slug]/derive.ts` | 197 |

## §15.1 — Knowledge view

- ✅ All **eight** categories rendered by iterating `KNOWLEDGE_CATEGORIES` (never a hardcoded list). Labels via exhaustive `Record<KnowledgeCategory,string>` in `categories.ts`.
- ✅ Structured entries per block (label/value `dl`), read-only text only.
- ✅ Per-location where applicable: blocks with `locationId !== null` are grouped and labelled with the location name (e.g. providers → "Northside — Main"); `locationId === null` blocks show "All locations".
- ⚠ Per-location blocks respect the active §2.4 global location filter (org-wide always show). Narrowest interpretation of "per-location where applicable" + §2.4's cross-tab filter.
- ✅ Categories with no block (e.g. Cedar's 5 unconfigured) still render, showing "No entries configured for this category yet" — all 8 remain visible.

## §15.2 — Change request workflow

- ✅ "Request an update" control on **every** knowledge block (`ChangeRequestForm` rendered per `KnowledgeBlockView`), not once per page.
- ✅ Form captures proposed change + reason (two `<textarea>`s — the only inputs in the tab).
- ✅ Submitting calls `recordKnowledgeChangeRequest(session, category)` → writes the `knowledge_change_request` audit event (§2.3). Proven by grep check 6.
- ✅ Status tracking through `requested → in_review → scheduled → live` using `KnowledgeRequestStatusChip` and `KNOWLEDGE_REQUEST_STATUSES` (imported, never redeclared).
- ✅ Version history list (what/when/who) from `fixture.knowledgeRequests[].history`, timestamps rendered in the location timezone via `formatDateTime`.
- ✅ Notification stub: the submitted view and the history section state plainly that a notification *would* be sent at each state change; no notification system built.

## SCOPE BOUNDARY — no self-serve editing

- ✅ Confirmed: **zero** self-serve editing built. Every value is read-only text (`dd`). No inline edit, no `contentEditable`, no save/`onSave`/`saveBlock`, no `<input>`. The only `<textarea>`s are the two change-request fields (grep check 5). The form proposes a change; it never mutates a knowledge value.

## §2.6 — Custom-agent route (`/agents/[slug]`)

- ✅ `page.tsx` is an async server component receiving `params: Promise<{ slug }>` and awaiting it (Next 15).
- ✅ Agent resolved from `fixture.agents` by slug via a `Map` lookup (no `slug ===` comparison, so no per-agent hardcoding — grep check 4 returns nothing).
- ✅ Unknown slug → `notFound()` (Next `not-found`), no empty page.
- ✅ Renders through `AgentAnalyticsPage`; every stat card is driven by `metricsContract: KpiDefinition[]`; `format` selects the `src/lib/format.ts` formatter.
- ✅ **No per-agent special-casing.** `derive.ts` is keyed purely by KPI `key`; `custom-agent-client.tsx` never names an agent. No `if (slug === …)`.
- ✅ KPI values derived generically from interactions attributed to the agent (`call.agent === entry.id`, location-scoped). Non-derivable metrics render `—` with a "not yet emitted" tooltip — never a fabricated number.
- ⚠ The seeded custom agent `post_op_followup` has **zero** attributed interactions (the `CallInteraction.agent` union structurally excludes custom ids), so all three of its KPIs (`followups_placed`, `reached_rate`, `complications_flagged`) render `—`. This is the honest "not yet emitted" degraded state and is exactly the §2.6 demo: a registry entry alone yields a full page. Stat cards still render from the contract (I do **not** use the template's whole-body `isEmpty`, which would hide them); only the chart/distribution slots show `EmptyState`.
- ✅ Primary chart: interactions over time (weekly). Distribution: triage outcome distribution using the frozen `TRIAGE_SERIES` binding (no inlined entity→color binding, THEME_NOTES §3). Drill-through: `/conversations/calls?agent={slug}`.

## Degraded / empty states

- ✅ NON-PHI: both surfaces are aggregate. Custom-agent route reads only aggregate call fields (agent, disposition, triage, duration, latency, timestamp); Knowledge reads only knowledge blocks/requests. No patient name, phone, recording, or transcript is rendered anywhere.
- ✅ Viewer: the §15 change-request control is not role-restricted (spec does not restrict it), so it stays available to all roles. `recordKnowledgeChangeRequest` has no permission gate.
- ✅ Cedar (`org_cedar`): 3 knowledge blocks render across 8 categories; `knowledgeRequests` empty → `EmptyState` renders in the change-request section. No custom agent → `/agents/post-op-followup` (and `/agents/post_op_followup`) resolve to no registry entry → `notFound()` (clean 404, no crash).

## Verification

- ✅ `npx tsc --noEmit` → exit 0.
- ✅ `npx eslint` (both scopes) → exit 0.
- ✅ Grep checks 2 (colors), 3 (any), 4 (per-agent) empty; 5 only the allowed textareas; 6 confirms the audit write.
