# AwaazLabs Client Dashboard Guide
### Agent-facing build & orchestration document — read this entire file before touching any code.

**Target repository/folder:** `Awaazlabs-Client-Dashboard`
**Source of truth for scope:** `qualicall_dashboard_spec.md` (the 19-section spec covering Sections 1–19). This guide is a strict operating manual for turning that spec into a fully hardcoded-data frontend inside the existing repo — nothing more, nothing less, same visual theme.

This document was produced by re-auditing every section of the spec against the build plan line by line. Where the earlier draft plan was vague or assumed capabilities that don't exist in the real tooling, it has been corrected here. Treat this version as authoritative.

---

## PART A — NON-NEGOTIABLE RULES (apply to every agent, every phase)

1. **The spec is the contract.** Every stat card, table column, filter, chart, drawer field, workflow action, empty state, and degradation rule listed anywhere in `qualicall_dashboard_spec.md` must exist in the shipped UI, traceable to a specific numbered subsection. If a UI element cannot be pointed at a spec line, it must be deleted. If a spec line has no corresponding UI element, the build is not done.
2. **Repo identity is fixed.** All work happens inside the `Awaazlabs-Client-Dashboard` repository/folder. Do not create a new project, do not scaffold a fresh app, do not rename the repo. Confirm you are inside `Awaazlabs-Client-Dashboard` (check `pwd`, `git remote -v`, and the package/project manifest name) before making any change.
3. **Theme is frozen.** No new colors, fonts, spacing units, border radii, shadows, or component visual language. Every new screen is built by composing the primitives that already exist in the repo. If a primitive genuinely doesn't exist (e.g. a "funnel" chart), extend the *closest existing primitive* using the *existing* token set — do not invent new styling. This is verified mechanically in Phase 3 (see Part D), not just by eyeballing.
4. **Data is hardcoded only.** No network calls, no real backend, no environment secrets. Every screen reads from local, version-controlled mock-data fixtures. Fixtures must be rich enough to demonstrate every state the spec describes for that screen: normal, empty, needs-attention/aging (red or amber), and NON-PHI-degraded where applicable.
5. **Canonical enums are declared exactly once.** Section 17 of the spec is implemented in a single shared file during Foundation. Every other file imports from it. Grep for hardcoded status strings in review — any duplicate enum declaration is a defect.
6. **Role and mode gating must be structurally real**, even against mock data — i.e., a Viewer role literally cannot render the fields the spec says a Viewer cannot see, and NON-PHI mode literally cannot render patient-level rows. This is not cosmetic hiding; the mock data-access layer itself must refuse to return the gated fields for the wrong role/mode, mirroring the spec's "UI hides, API independently rejects" principle from Section 2.2.
7. **Every gated action writes an audit event**, per Section 2.3, into a single shared in-memory/local audit store that the Audit Log tab (16.2) reads from. Do not fake the Audit Log tab with its own static fixture — it must be fed by real actions elsewhere in the app.
8. **File/route ownership is exclusive per work item.** Before any two pieces of work run concurrently, confirm they touch disjoint files and routes. If two tasks need to touch the same shared file (enums, theme, layout shell, mock-data schema, shared primitives), that file is Foundation-phase-only and frozen (read-only) for everyone else afterward — do not schedule those tasks concurrently.
9. **No task is "mostly done."** Each task ends with the self-audit described in Part D for that scope, and a completion note is written before moving on. Silent partial completion is treated as a failure of the task.
10. **When the spec is ambiguous, do not guess silently.** Record the ambiguity, the interpretation chosen, and the reasoning in `BUILD_NOTES.md` at the repo root, so it can be checked against the spec by a reviewer later. Do not invent scope to resolve ambiguity — pick the narrowest reading that satisfies the literal spec text.

---

## PART B — SKILLS: what to check, what to use, what to install

This build touches design-system consistency, large structured data tables, charts/visualizations, accessibility, and repo hygiene — all areas where a dedicated skill measurably improves output quality. Do this before Phase 0 starts:

1. **Inventory installed skills.** Run `/skills` (or list `.claude/skills/` in the repo and `~/.claude/skills/` for user-level skills) to see what's already available in this environment.
2. **Confirm/install a frontend design-system skill.** This build lives and dies on "same theme, composed correctly." If no design-system/UI-consistency skill is installed:
   - Check the official marketplace first: `/plugin marketplace add anthropics/claude-plugins-official` (or `/plugin marketplace update claude-plugins-official` if already added), then browse with `/plugin` → Discover, or install directly if the exact plugin name is known, e.g. `/plugin install <plugin-name>@claude-plugins-official`.
   - If nothing suitable exists there, search community marketplaces (e.g. `/plugin marketplace add <org>/<marketplace-repo>` for a known catalog) for a UI/design-system-extraction or component-library skill.
   - If still nothing fits, **write a project-scoped skill**: create `.claude/skills/awaazlabs-theme/SKILL.md` in the repo, containing the exact design tokens, component inventory, and composition rules extracted in Phase 0 (Part C.1). This makes theme discipline something every subsequent agent automatically loads, instead of something each one has to be told by hand every time.
3. **Confirm/install a skill for large structured tables and charts** (many tabs in this spec are dense tables, funnels, heatmaps, and trend lines with markers). If nothing installed covers this, either install a relevant community skill the same way as above, or document the chosen charting approach as part of the shared component primitives in Foundation (Part C.2) so it doesn't need to be re-derived per tab.
4. **Confirm/install an accessibility or code-review skill** if available, to run during Phase D QA (masked/reveal controls, drawers, and dense tables are common a11y failure points).
5. **Do not install anything you haven't checked the description of.** Installed plugins can run scripts; read what a skill does before installing it, per standard plugin hygiene.
6. **Record what was installed or written** in `BUILD_NOTES.md`: skill name, source, and why it was chosen. This is part of the audit trail, same as any other build decision.
7. If the environment cannot install anything (no marketplace access), **do not block** — fall back to the project-scoped `SKILL.md` you write yourself in step 2/3. A hand-written skill file that correctly encodes the repo's real tokens and primitives is strictly better than an unverified third-party one anyway.

---

## PART C — ORCHESTRATION MODEL (corrected to match how subagents actually work)

**Important correction from the earlier draft:** subagents run inside one orchestrating session and **cannot themselves spawn further subagents** — there is no nested delegation in the standard model. All fan-out is issued directly by one orchestrator (you, the main agent, or a human running the session). For a build this size there are two valid ways to get real parallelism; pick based on what's available in the environment:

- **Option 1 — Flat subagent fan-out (works everywhere, default choice):** the orchestrator directly launches multiple subagents in the same turn/session for independent, disjoint-file tasks, waits for them to report back, integrates, then launches the next batch. This is turn-by-turn delegation, not persistent teams, but it's real concurrent execution for the duration of a batch.
- **Option 2 — Agent Teams (only if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is enabled in this environment):** the orchestrator becomes a "team lead" and instantiates teammates with independent, persistent context who can message each other directly. Use this only for the sustained, high-volume Phase 2 work below if the environment supports it; if unsure, default to Option 1 — do not assume Agent Teams is available.

Either way, **the phase structure and blocking gates below do not change** — only how "parallel" is implemented changes.

```
PHASE 0 — DISCOVERY            (orchestrator itself, or one subagent; sequential, blocking)
PHASE 1 — FOUNDATION           (orchestrator itself, or one subagent; sequential, blocking)
PHASE 2 — BUILD BATCHES        (flat parallel subagents / team, grouped 2A..2E; see below)
PHASE 3 — INTEGRATION & AUDIT  (orchestrator itself; sequential, blocking)
PHASE 4 — FINAL QA             (orchestrator itself; sequential)
```

**Concurrency guidance:** do not launch more than ~5 subagents at once regardless of which option is used — over-parallelizing wastes tokens/compute and creates coordination overhead with no quality benefit here, since each Phase 2 batch is already file-disjoint. If a batch would need more than 5 tabs worked simultaneously, split it into two sequential sub-batches instead of exceeding 5 concurrent agents.

**Every subagent invocation must include, explicitly, in the prompt (this is the single biggest failure point in real usage — under-specified subagent invocations produce vague or wrong output):**
- The exact repo path/branch/worktree it should work in (see Part C.4).
- The exact spec subsection(s) it owns, pasted or referenced precisely — not "build the VOB tab," but the literal bullet list from Section 7/8.
- The exact files/routes it is allowed to touch, and the explicit instruction not to touch shared/frozen files.
- The exact shared primitives/enums it must import from, with their paths.
- The exact self-audit checklist it must complete before reporting done (Part D).
- A requirement to return a structured summary (files touched, spec bullets covered, any ambiguity logged), not a narrative.

### C.1 Branching/worktree discipline
Because multiple agents may touch the repo concurrently, use one git worktree or branch per concurrently-running task, named after the spec section it owns, e.g. `feature/section-04-overview`, `feature/section-07-vob-agent`. Never let two concurrently-running agents share a working tree. Integration (Phase 3) is where these merge back to the main build branch — not before.

---

## PART D — SELF-AUDIT PROTOCOL (required at the end of every phase and every batch)

Every agent, before declaring a task complete, must:
1. Re-open the exact spec subsection(s) it was assigned and go bullet by bullet.
2. For each bullet, state ✅ (built, matches exactly), ⚠️ (built but diverges — explain how), or ❌ (missing) — no bullet may be skipped.
3. Confirm no UI element exists in its scope that isn't traceable to one of those bullets.
4. Confirm every visual element uses existing shared tokens/primitives (no new colors/spacing/components).
5. Confirm mock data covers: a normal-state row, an empty state, and (where the spec defines one) a needs-attention/aging/red-accent state.
6. Write this checklist into `progress/<section-name>_audit.md` (create a `progress/` folder at repo root if it doesn't exist) and only then report the task as done.

This produces a running, file-based paper trail that Phase 3 consumes directly instead of having to re-derive coverage from scratch.

---

## PART E — PHASE 0: DISCOVERY (single pass, blocking)

Work inside `Awaazlabs-Client-Dashboard`. Do not modify anything in this phase — read-only.

1. **Confirm identity:** verify the working directory is in fact `Awaazlabs-Client-Dashboard` before doing anything else.
2. **Inventory the current app:** every route/page, every shared component (buttons, cards, tables, badges, drawers, charts if any), the theming source (tailwind config / CSS variables / design-token file / styled-components theme — whatever the repo actually uses), the routing/nav configuration, and any existing mock-data convention.
3. **Extract exact design tokens** (colors, spacing scale, radii, shadows, typography, breakpoints) **verbatim** — copy real values, don't paraphrase — into `THEME_NOTES.md` at repo root. This file is what Part B's design-system skill (installed or hand-written) should be built from.
4. **Diff current nav vs. spec Section 3's exact nav tree** (see Part F.2 for the literal tree). Produce three lists in `discovery_report.md`: `KEEP`, `REMOVE` (exists now, not in spec — must be deleted), `ADD` (in spec, not built yet).
5. **Diff current pages vs. the spec's 19 sections** the same way.
6. **List existing reusable primitives** vs. what Section 3.5 downstream primitives (Part F.3) require, so Foundation knows exactly what to build vs. extend vs. reuse.
7. **Output:** `discovery_report.md` (nav diff, page diff, primitive gap list) and `THEME_NOTES.md` (verbatim tokens), both committed to the repo root.

**Gate:** Foundation may not start until both files exist and have been reviewed.

---

## PART F — PHASE 1: FOUNDATION (single pass, blocking — highest-risk phase, get it exactly right)

### F.1 Canonical status enums (spec Section 17 — implement verbatim, no paraphrasing, no additions)
Create one file, e.g. `src/shared/status-models.ts` (or the repo's real equivalent path/language):
- **Appointment:** `booked → confirmed → (rescheduled loops to confirmed) → completed | cancelled | no_show`
- **VOB** (per spec 7.3): `queued → in_progress (dialing, on_call, pending_callback) → terminal`; terminal states: `verified, partial_coverage, needs_authorization, needs_referral, not_covered, inactive_policy, member_not_found, unable_to_verify`
- **Escalation:** `open → acknowledged → resolved`
- **Review request:** `eligible → called → reached → asked → agreed → link_sent → posted | declined | opt_out`
- **Campaign contact:** `queued → attempted → reached → booked | exhausted | opt_out`
- **Flag:** `submitted → under_review → resolved`
- **Optimization event:** `detected → in_tuning → deployed → verified`
- **Call disposition:** `booked, info_only, verified, confirmed, review_requested, reengaged_booked, escalated, voicemail, no_answer, abandoned`

Every status chip, filter option, and badge anywhere in the app imports from this one file. A grep for any duplicate/local status string constant elsewhere in the codebase after Phase 2 is a hard defect.

### F.2 Navigation shell — build exactly this tree, nothing more, nothing less (spec Section 3)
- **HOME:** Overview
- **OPERATIONS:** Appointments · Conversations (sub-views: Calls, Chats) · Escalations · VOB Queue
- **AGENTS:** Receptionist · VOB Agent · Chat Agents · Review Taker · Reengagement · *(registry-driven slot for custom agents, per 2.6)*
- **QUALITY:** Quality and Optimization · Agent Knowledge
- **GROWTH:** Reviews · Campaigns
- **INSIGHTS:** Reports and Exports
- **COMPLIANCE** (PHI mode only): Audit Log
- **SETTINGS:** Members · Usage and Billing · Organization and Locations · Lines and Numbers · Consent and Do-Not-Call · Notifications

Top bar: organization switcher (multi-org users), location filter, mode badge (NON-PHI / PHI-BAA), notifications bell, user menu — per spec Section 3. Delete every current nav item on the Phase 0 `REMOVE` list; add every item on the `ADD` list; touch nothing else.

### F.3 Global mechanics to build in Foundation
- **Mode badge + NON-PHI degradation (2.1):** a togglable mock mode that switches every gated tab between full detail and its documented aggregate-only/hidden state (5.6, 10.4, etc.). This must be exercised, not assumed, in every downstream tab.
- **Role gating (2.2):** a switchable mock "current user" for Owner/Admin, Manager, Viewer. Gate at the mock data-access layer (per Rule 6 in Part A), not only in the render layer.
- **Location filter (2.4):** global, persists across tabs; hidden entirely for a single-location mock org, shown for a multi-location mock org; every relevant mock row carries `location_id`.
- **Audit event writer (2.3):** one shared function/store that every gated action calls: login, phone-number reveal, recording playback, transcript view, patient search, export, note edit, appointment status change, VOB queue action, knowledge change request, consent list change, permission change. This feeds Audit Log (16.2) with real generated rows.

### F.4 Mock data schema
- Two mock organizations: one single-location, one multi-location, to prove the location filter behavior both ways.
- A shared patient/contact fixture shape matching the Section 2.5 data envelope **exactly**: first name, last name, masked phone (click-to-reveal, audited), insurance carrier + member context, treatment/service interest, language, operational metadata (timestamps, statuses, agent attribution). The schema must make it **structurally impossible** to add DOB, SSN, clinical notes, or diagnosis fields — don't just omit them by convention, don't define the fields at all.
- Agent registry entries (2.6): name, type, channel, icon, metrics contract, for Receptionist, VOB Agent, Chat Agents, Review Taker, Reengagement, **plus one sample custom agent** proving the "zero frontend work" claim in 2.6 actually renders via the standard template.

### F.5 Shared primitives to build/extend and register (needed by multiple Phase 2 batches — build once here)
- Stat card (with delta variant, and a tooltip-formula variant for computed/estimate cards like 4.3)
- Standard agent-analytics page template per 2.6 (stat cards row + one primary chart + one distribution component + drill-through)
- Status distribution horizontal bar (reused in 4.2, 7.2, others)
- Funnel component (needed by 13.1, 14.1)
- Four-stage loop/stage graphic with live counts and per-stage click-through (needed by 12.1)
- Trend line with plotted event markers overlay (needed by 12.2)
- Hour-of-day / day-of-week heatmap (needed by 6.2, 14.1)
- Slide-over detail drawer shell (needed by 5.4, 8.2, 10.1, 10.2)
- Masked-value-with-reveal control, audited on reveal (phone numbers)
- Aging/SLA badge, amber past threshold 1, red past threshold 2 (needed by 8.1, 4.6, 11.2)
- Dismissible banner (needed by 4.6, 5.6)

**Gate:** write `FOUNDATION_DONE.md` at repo root listing every file created/extended for F.1–F.5, plus confirmation that mode/role/location/audit-writer are demonstrably working (not just present). Phase 2 batches may not start until this file exists and every item in it is checked off.

---

## PART G — PHASE 2: BUILD BATCHES (parallel per Part C; each batch below = one subagent, further splittable per tab if within the 5-concurrent cap)

Every batch/tab below **must** import enums/components from Foundation — never redeclare them. Every batch ends with the Part D self-audit written to `progress/<name>_audit.md`.

### Batch 2A — Core Operations (Sections 4, 5)
- **Overview (4):** exactly six subsections, in this order:
  - A) Appointments: 4 stat cards (booked today w/ delta, booked this week w/ booking rate, upcoming next 7 days, no-shows/cancellations this week w/ rate — this card must hide rather than show a misleading zero when data is unavailable) + bookings-over-time chart, 7D/30D toggle, stacked by source (Voice/WhatsApp/Web Chat).
  - B) VOB status: 3 stat cards (in progress w/ sub-statuses, completed today/this week w/ verified rate, needs-attention sum w/ red accent + click-through to pre-filtered VOB Queue) + compact horizontal status distribution bar.
  - C) Revenue recovered: one estimate card, formula = (after-hours bookings + reengagement bookings + recovered no-shows) × configured avg appointment value; hides if avg value unset; tooltip shows formula and inputs.
  - D) Quality pulse: current aggregate grade, 30-day sparkline, optimization-event count this month, click-through to Quality tab.
  - E) Operational telemetry: interactions row (per-agent + Overall/All), calls/minutes today, avg duration, avg cost/interaction, calls-over-time + minutes-over-time charts (7D/30D), avg first-audio response (ms) w/ 800ms target line, success rate w/ counts, live calls now w/ refresh timestamp.
  - F) Attention banner: dismissible, red, conditional on any of the four documented triggers, each deep-linking to its owning surface.
- **Appointments (5):** header stats strip (booked today, upcoming 7 days, confirmation rate, no-show rate trailing 30 days); table with all 13 documented columns exactly; documented filters; detail drawer with all 8 documented sub-items (full record w/ unmask, originating interaction link, VOB card, confirmation/reminder history, timeline, manual Completed/No-show buttons, staff notes, flag button); calendar view (day/week, no drag-to-reschedule); documented empty/degraded/NON-PHI states.

### Batch 2B — Agent Analytics (Sections 6, 7, 9, 13.1, 14.1) — up to 5 sub-agents, one per tab, using the Section 2.6 template from Foundation
- **Receptionist (6):** all 8 stat cards; triage donut; intake-method donut; language-mix bars; bookings-by-hour heatmap split business/after-hours; booking-rate trend 7D/30D; drill-through to Conversations>Calls scoped to Receptionist.
- **VOB Agent (7):** all stat cards including the 3-way benefit-capture completeness sub-bars; VOB status distribution bars; verifications-over-time; payer breakdown table (must be visually prominent — this is explicitly called out as the first thing a billing-company buyer checks).
- **Chat Agents (9):** all stat cards including the paired containment/resolution rule — these two cards must render adjacent with a shared caption, not as two unrelated cards; grouped bar chart (containment/resolution/deflection/escalation); sessions-over-time by channel; intent distribution; language mix; drill-through to Conversations>Chats.
- **Review Taker analytics (13.1):** full 7-stage eligibility funnel exactly as listed; all stat cards; compliance note rendered in-UI (every eligible patient gets the ask, no sentiment pre-filter); private-feedback list fed from negative-experience routing.
- **Reengagement analytics (14.1):** full 6-stage funnel; all stat cards including the revenue estimate that feeds Overview's 4.3 card (confirm this cross-tab number actually matches); best-contact-window heatmap.

### Batch 2C — Worklists & Records (Sections 8, 10, 11)
- **VOB Queue (8):** worklist table, all 10 documented columns + amber(24h)/red(48h) aging indicator; row detail drawer (captured benefits, prior auth/referral flags, per-attempt call log w/ recordings+transcripts, payer reference numbers); 4 row actions (Retry, Mark resolved w/ reason picker, Escalate, Add note) each writing an audit event and updating the status timeline; queue-level filters, bulk retry, audited CSV export.
- **Conversations (10):** Calls sub-view (all documented columns; drawer with audio player, transcript w/ PII redaction markers, consent-disclosure event when two-party mode active, inline QA grade breakdown per 12.3, linked objects, flag button); Chats sub-view (thread list, thread detail w/ handoff markers); shared filter bar; NON-PHI aggregate-only degradation.
- **Escalations (11):** table w/ all documented columns; acknowledgement workflow (one-tap, audited, outcome note); default thresholds (30 min Urgent / 4 hr otherwise) wired into the Overview attention banner; stat strip.

### Batch 2D — Quality, Growth & Knowledge (Sections 12, 13.2, 14.2, 15) — this batch contains the centerpiece screen; give it the most review attention
- **Quality and Optimization (12):** 4-stage loop header w/ live counts and per-stage click-through; aggregate quality (score, 30/90-day trend w/ optimization events plotted as markers, grade distribution histogram, per-agent quality table); the 5 grading dimensions rendered as the per-call breakdown (Accuracy, Compliance, Conversation quality, Task completion, Efficiency); optimization events timeline in client-safe language, controlled vocabulary, using the Optimization-event enum from Foundation, with grade delta shown per event — internal tuning mechanics must never be exposed; flagged interactions inbox (submitted/under review/resolved w/ resolution note); compliance sub-panel (3 rate metrics). **Mock data requirement, non-negotiable:** seed at least one full `detected → in_tuning → deployed → verified` cycle showing a visible, plotted grade lift — this is explicitly required demo data in the spec's build-priority section.
- **Reviews (13.2):** rating trend chart w/ go-live annotation line; reviews-over-time (attributed vs organic, stacked); recent attributed reviews list; private feedback list; multi-location comparison table. Do **not** build review-response, listings-management, or social-publishing features — the spec explicitly scopes these out.
- **Campaigns (14.2):** campaign list (all documented columns); campaign detail (funnel identical to 14.1 scoped to campaign, audience definition summary, per-contact rows, pacing settings, pause/resume audited controls, read-only guardrail display); request-to-Awaaz stub for audience creation — do not build self-serve segment building, the spec explicitly defers it.
- **Agent Knowledge (15):** read-only structured knowledge view across all 8 documented categories; change-request workflow (request button, status tracking through the documented states, notification stub, version history). Do **not** build self-serve editing — the spec explicitly forbids it in this build.

### Batch 2E — Settings, Insights & Compliance (Section 16) — up to 6 sub-agents, one per sub-tab
- **Reports and Exports (16.1):** scheduled reports config (weekly/monthly, per-location + consolidated variants); on-demand CSV export buttons per operational table, role-gated to Owner/Manager, each writing an audit event with row-count and filter parameters; monthly business-review-pack mock generator.
- **Audit Log (16.2, PHI mode + Owner only):** table w/ exact documented columns; documented filters; export (itself audited). **This tab must read live from the Foundation audit-writer store, not from its own static fixture** — build it only after F.3's audit writer exists and is wired into every other batch's gated actions.
- **Members (16.3):** user list (role, last active, MFA status); invite-by-email w/ role assignment (Owner only); audited role changes.
- **Usage and Billing (16.4):** minutes vs. plan w/ projection; breakdown by agent/location; chat-sessions meter (separate from voice minutes); overage indicator + history; invoice list w/ download. No plan/price editing.
- **Organization/Locations, Lines/Numbers, Consent/DNC (16.5):** org profile + avg-appointment-value config (confirm this literally feeds the Overview 4.3 card); location list w/ timezone/hours/holidays; line health indicators; suppression list w/ audited manual add/remove; quiet-hours config.
- **Notifications (16.6):** full event-type × channel × role preference matrix; Owner escalation alerts locked on, cannot be fully disabled.

---

## PART H — PHASE 3: INTEGRATION & LINE-BY-LINE AUDIT (single pass, blocking)

This phase builds nothing new. Its only job is merging and verifying.

1. Merge every batch's branch/worktree into the main build branch. Conflicts should be near-zero if Part C.1 file-ownership discipline was followed; resolve any that occur without altering scope.
2. Walk `qualicall_dashboard_spec.md` section by section, Sections 1–19, and produce `spec_coverage_audit.md`: one row per spec bullet, status ✅/⚠️/❌, pulling directly from the `progress/*_audit.md` files written in Phase 2 and re-verifying each one against the merged codebase (do not just trust the self-reports — spot-check).
3. Re-run the Phase 0 nav/page diff against the final merged build. Zero `REMOVE` items may remain; zero unlisted extras may exist anywhere (routes, nav items, stat cards, columns, buttons).
4. Verify every explicitly-named cross-tab wiring point actually works against the mock data:
   - Overview quality pulse ↔ Quality tab's current score
   - Overview revenue estimate ↔ Organization's configured avg appointment value
   - VOB status chip consistency across Overview, VOB Agent tab, VOB Queue, and the Appointments table chip (all four must read the same canonical enum values for the same mock record)
   - Every documented "click-through" / "drill-through" actually navigates and pre-filters correctly
   - Every Flag button ↔ the Section 12.5 flagged-interactions inbox
   - Every audited action anywhere in the app ↔ a corresponding row in Audit Log
5. Verify theme consistency: no colors/fonts/spacing outside `THEME_NOTES.md`; every new screen uses shared primitives from Foundation, not one-off styling.
6. Fix everything flagged ❌/⚠️ directly if the fix is small and targeted. If a fix would require re-architecting a batch's work, flag it explicitly for Phase 4 rather than silently patching around it.

**Gate:** Phase 4 does not start until `spec_coverage_audit.md` exists and every ❌ has either been fixed or explicitly escalated with a reason.

---

## PART I — PHASE 4: FINAL QA (single pass)

1. Click through the entire nav tree in both mode states (NON-PHI / PHI-BAA) and all three roles (Owner, Manager, Viewer), confirming degradation/gating matches the spec exactly on every single tab — not spot-checked, every tab.
2. Confirm the spec's own "demo spine" (build-priority items 1–6: global shell, Overview, Appointments, canonical enums wired into VOB tab + VOB Queue, Conversations, Quality loop) is airtight — the spec calls these non-negotiable.
3. Confirm the seeded Quality-tab optimization cycle (detected → verified, visible grade lift) renders correctly end-to-end.
4. Confirm `spec_coverage_audit.md` now reads 100% ✅. Anything still ❌/⚠️ is reported back explicitly — never shipped silently.
5. If an accessibility skill was installed/available per Part B, run it now against the dense tables, drawers, and masked-reveal controls.
6. Produce `BUILD_SUMMARY.md` at repo root: what was built, which primitives were extended, every ambiguity encountered and how it was resolved (cross-reference `BUILD_NOTES.md`), which skills were used or written, and final coverage-audit status.

---

## PART J — DEFINITION OF DONE (final checklist)

- [ ] Confirmed working inside `Awaazlabs-Client-Dashboard`, no new project scaffolded.
- [ ] `discovery_report.md` and `THEME_NOTES.md` exist and were reviewed before Foundation started.
- [ ] Design-system skill installed or hand-written and referenced in `BUILD_NOTES.md`.
- [ ] `FOUNDATION_DONE.md` exists; enums/nav/mode/role/location/audit-writer/mock-schema/primitives all present and demonstrably working.
- [ ] Every one of the 19 spec sections has a corresponding, reachable, fully-populated UI surface.
- [ ] Every stat card, column, filter, chart, drawer field, and workflow action listed in the spec exists — nothing extra, nothing missing.
- [ ] Mock data demonstrates every documented state per tab (normal, empty, needs-attention/aging, NON-PHI-degraded where applicable).
- [ ] Canonical enums declared exactly once and imported everywhere else.
- [ ] Role and mode gating are structurally enforced at the mock data-access layer, not just visually hidden.
- [ ] Every gated action produces a real row in Audit Log.
- [ ] Existing theme untouched; every new screen composed from existing (or Foundation-registered) primitives only.
- [ ] `spec_coverage_audit.md` is 100% ✅.
- [ ] `BUILD_SUMMARY.md` and `BUILD_NOTES.md` are complete and committed.
