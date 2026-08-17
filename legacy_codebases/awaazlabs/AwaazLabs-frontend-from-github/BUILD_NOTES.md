# BUILD_NOTES.md

Running log of every decision, ambiguity, and interpretation, per guide Part A Rule 10 and
Part B item 6. Reviewable against the spec by a third party.

---

## A. Decisions made with CTO approval

| # | Decision | Rationale |
|---|---|---|
| A1 | Repair three broken theme tokens (`--input`, `--card-foreground`, `--popover-foreground`) and the escaped `&amp;` Tailwind variants in `table.tsx`; make `cn()` use `tailwind-merge`. | Defects D1–D4 in `discovery_report.md`. A dead CSS variable is not a design decision. "Theme is frozen" protects design intent, not broken bytes. |
| A2 | Upgrade Next 14.2.35 → 15.5.20, React 18 → 19.2.7. | Clears all 9 Next.js security advisories. Aligns with the `Next.js 15` line in `CLAUDE.md`. Done before feature code existed, so no migration debt. |
| A3 | Remove 7 unused Radix packages + `react-hook-form` + `zod`. Keep `dialog`, `select`, `popover`, `dropdown-menu`. | All nine were installed and never imported. Unused deps are attack surface and React-19 peer-dep risk. The four retained are used for focus-trap/ARIA correctness in drawers, filters, and menus. |
| A4 | Add a 6-slot categorical chart palette, a 5-step sequential ramp, and one amber status token. | The spec mandates multi-series charts; the frozen theme has 3 usable hues. Rendering a 4-series stacked chart in 3 colors is impossible. Fully specified and validated in `THEME_NOTES.md` §3–§5. |
| A5 | Charts are hand-rolled SVG, not a charting library. | Zero new dependencies; SSR-safe with no hydration risk; `fill="var(--chart-1)"` flows theme tokens straight through, so the Phase 3 mechanical "no colors outside THEME_NOTES" check passes natively. ~6 of the ~20 required chart forms (funnel, heatmap, loop graphic, distribution bar) have no library implementation and would be hand-built regardless. |
| A6 | Standalone `git init` inside `Awaazlabs-Client-Dashboard`; no worktrees. | CTO confirmed this becomes its own repo. Worktrees exist to stop two agents writing one file; every Phase 2 batch creates new files under its own route folder, so there is nothing to collide on. |
| A7 | Milestone 1 = the spec's own §19 "demo spine" (items 1–6). Everything else renders a real Under Construction page inside the correct nav slot. | CTO requirement: a deployable, reviewable 50% that can have a backend wired behind it. §19 explicitly calls items 1–6 non-negotiable. |
| A8 | Dark mode out of scope. | Scaffold ships none; spec never mentions it. A dark palette must be *selected and re-validated*, not flipped. Flagged as follow-up rather than half-implemented. |
| A9 | The mode and role **switchers** live inside the user menu under a visible "Demo controls" heading; only the mode **badge** sits in the top bar. | §3's top bar has five items and a mode *badge* is one of them — not a switcher. §2.1 says mode is "set by Awaaz admins per organization, never self-serve." But guide Part F.3 requires both to be togglable so every gated surface can be exercised. Putting the toggles behind a labelled "Demo controls" heading satisfies the guide without adding a sixth item to §3's top bar or implying a capability the product does not have. |
| A10 | `RouteGuard` takes a string capability key, not a predicate function. | A `page.tsx` is a React Server Component. Passing `allow={canSeeAuditLog}` — a function — into a client component is not serializable and fails the build. The lookup happens on the client instead. |
| A11 | Added `src/components/route-guard.tsx`, which the spec does not name. | §2.2: "The UI hides what the role cannot access; the API independently rejects it." Hiding a nav link is not access control — `/audit-log` is reachable by typing the URL. This is the route-level half of that sentence; `data-access.ts` is the data-level half. Neither is sufficient alone. |

---

## B. Spec ambiguities and contradictions — interpretation chosen

Per Rule 10, the **narrowest reading that satisfies the literal spec text** is chosen, and
where the guide and the spec disagree, **the spec wins** (guide Part A Rule 1: "the spec is
the contract").

### B1 — Audit Log section number is wrong in §2.3
§2.3 reads "The Audit Log tab (Section 15) is the read surface." But §15 is *Agent
Knowledge*; Audit Log is §16.2.
**Interpretation:** typo. Audit Log = §16.2. The guide agrees.

### B2 — "Verifier" is an agent that does not exist in the catalog
§1.4 lists exactly five standard agents: Receptionist, VOB Agent, Chat Agents, Review
Taker, Reengagement. But §2.8 says "all outbound agents (Verifier, Review Taker,
Reengagement)", §5.4 says "each Verifier attempt", and §10.1's agent column lists
"Receptionist, VOB, Verifier, Review Taker, Reengagement" — treating VOB and Verifier as
*separate* values.
**Interpretation:** `Verifier` is a distinct outbound agent responsible for **appointment
confirmation and reminder calls** (§5.4 describes its attempts producing outcomes
`reached, voicemail, no answer, confirmed, reschedule requested` — appointment outcomes,
not insurance outcomes). It is *not* the VOB Agent, which verifies insurance. It gets a
registry entry and appears in the Conversations agent dimension, but it gets **no nav tab
of its own** — §3's AGENTS group does not list it, and inventing one would be adding scope.
This is the narrowest reading that makes §2.8, §5.4, and §10.1 all literally true.

### B3 — Review Taker funnel: 8 stages in the spec, "7-stage" in the guide
Spec §13.1: `completed appointments > eligible > called > reached > review ask delivered >
agreed > link sent (SMS) > review posted (attributed)` — that is **8** nodes. The guide's
Batch 2D says "full 7-stage eligibility funnel exactly as listed."
**Interpretation:** build **8** stages as literally enumerated in the spec. The guide's
count is a miscount of the list it points at; the spec is the contract.

### B4 — Appointments table: 12 columns in the spec, "13" in the guide
Spec §5.2 enumerates: date/time, patient name, phone, treatment, source, language,
insurance captured, VOB status chip, triage flag, status, booked by, location — **12**.
Guide Batch 2A says "all 13 documented columns exactly."
**Interpretation:** build the **12** columns the spec enumerates. Adding a 13th to satisfy
the guide's count would violate Rule 1 ("if a UI element cannot be pointed at a spec line,
it must be deleted").

### B5 — "Recovered no-shows" is undefined (§4.3)
The revenue formula is `(after-hours bookings + reengagement bookings + recovered
no-shows) × avg appointment value`. "Recovered no-show" is never defined.
**Interpretation:** an appointment whose status reached `no_show`, and for which a
subsequent appointment was later booked for the same contact within the reporting period.
The tooltip (§4.3 requires one showing "the formula and inputs") states this definition
verbatim, so the reader is never misled about what the estimate counts.

### B6 — §2.7 requires an i18n framework "in place day one"  ✅ RESOLVED
"UI ships English; the i18n framework is in place day one with Spanish as the second
locale target." No guide batch owns this, and no spec section describes a language switcher.

**Initially deferred and reported as an open item. Now built** (`src/i18n/`), because the
sentence is a spec requirement, not a nice-to-have.

Interpretation, held to the sentence's exact words:

- *"The i18n framework is in place"* — `LocaleProvider`, a typed catalogue per locale, and
  `useTranslations()`. **Zero new dependencies**: `next-intl` and `react-i18next` each bring
  a routing model (`/es/...` segments) that appears nowhere in §3's nav tree.
- *"UI ships English"* — `DEFAULT_LOCALE = 'en'`. Application **chrome** (navigation, top
  bar, placeholder and denial states) is translated. Page bodies remain English. Extending
  coverage means adding keys, not restructuring.
- *"with Spanish as the second locale target"* — `es.ts` exists and is typed
  `Record<MessageKey, string>`, so a key added to `en.ts` without a Spanish translation is a
  **compile error**. There is no silent English fallback; an untranslated string cannot reach
  a Spanish-speaking user by accident.
- *"Language of patient interactions is a data dimension throughout, separate from UI
  locale."* — two distinct types. `Language` (`en | es | other`) sits on every contact and
  drives the §6.2/§9.2 language-mix charts. `Locale` governs the UI. A clinic whose staff
  read English still sees that 22% of its calls were in Spanish. Conflating them would have
  been the easy mistake.

The locale persists across reloads (`localStorage`) and updates `<html lang>`, so assistive
technology never announces Spanish content as English. Verified in a real browser.

### B7 — Roles: is "Owner/Admin" one role or two?
§2.2 says "Three roles minimum at launch" then lists `Owner/Admin`, `Manager`, `Viewer`.
But §16.2 says Audit Log is "Owner only" and §16.3 says invites are "Owner only".
**Interpretation:** one role named `OWNER_ADMIN`, matching "three roles". Where the spec
says "Owner only" it means this role. No separate Admin role is created.

### B8 — Viewer sees the appointment list but not patient data
§2.2: "Viewer: aggregate analytics and appointment list; no recordings, no transcripts, no
phone-number reveal, no exports."
**Interpretation:** Viewer *can* load `/appointments` rows. The mock data-access layer
returns those rows with `phone` **absent from the object entirely** (not masked, not
`null`) — per Rule 6, gating is structural, so a Viewer cannot reveal what was never
returned. Recording URLs and transcripts are likewise omitted from the payload.

### B9 — Overview §4.1 no-show card "hides rather than shows a misleading zero"
**Interpretation:** the mock org exposes an `outcomeDataAvailable: boolean`. When false the
card is not rendered at all. The multi-location demo org sets it true; a dedicated fixture
state proves the hidden case, per guide Part D item 5.

### B10 — §12.1 loop stage "Optimizations applied" vs §17 enum `deployed`
The loop's fourth stage is "Optimizations applied"; the canonical Optimization-event enum
is `detected → in_tuning → deployed → verified`.
**Interpretation:** "Optimizations applied" counts events whose status is `deployed` **or**
`verified` (both have been applied; `verified` additionally has a measured grade delta).
The loop's stage-3 "Flagged for optimization" counts `detected` or `in_tuning`.

### B11 — Triage color: the spec specifies the table chip, not the donut
§5.2 says "Triage flag (None, Low, High, Urgent; **red accents on High and Urgent**)". §6.2
requires a "triage distribution donut" but says nothing about its colors.
**Interpretation:** the **table chip** renders High and Urgent both in `--destructive`,
exactly as §5.2 states. The **donut** treats triage as ordinal severity and ramps
None → `--border`, Low → `--muted-foreground`, High → `--status-warning`, Urgent →
`--destructive`, because four donut segments must be mutually distinguishable and §6.2
imposes no constraint. This is deliberately two renderings of one dimension; recorded here
rather than silently reconciled, per Rule 7.

### B12 — `verified` VOB status wears a categorical green
The dataviz rule is that a series which *means* good or bad wears a status token, never a
categorical one. The theme has `--destructive` (bad) and `--status-warning` (warning) but
**no success token**, and adding one was not approved.
**Interpretation:** `verified` uses `--chart-4` (green, 4.95:1). It reads correctly and is
validated, but it is a categorical token doing status work. If a `--status-good` token is
ever added, this should move to it. Logged as a follow-up, not a silent choice.

### B13 — `Sparkline` does not render through `ChartFrame`
Every chart renders through `ChartFrame`, which supplies the legend and screen-reader table
that make the sub-3:1 series colors legal. A sparkline is an inline `role="img"` glyph with
no axes and cannot also be a framed `<figure>`.
**Interpretation:** `Sparkline` is exempt. This is safe, not a loophole: the relief rule
binds only on colors below 3:1, and the sparkline's single series is `--chart-1` at 4.42:1.
It carries a required `ariaLabel` instead.

### B14 — Flagging an interaction is not an audited event
Guide Part A Rule 7 says "every gated action writes an audit event". §12.5 requires the
Flag button to feed the flagged-interactions inbox. But §2.3 enumerates **exactly twelve**
audited event types, and `flag` is not among them.
**Interpretation:** flagging writes to a dedicated flag store (`src/shared/flag-store.ts`),
not to the audit log. Adding a thirteenth `AuditEventType` would contradict §2.3's explicit
list, and the guide's Rule 7 is scoped to "gated" actions — flagging is available to every
role, so it is not gated. The §12.5 inbox therefore reads seeded history plus every flag
raised this session, satisfying "fed by real actions, not a static fixture."

### B15 — VOB status distribution renders three groups, not twelve statuses
§7.2 asks for a "VOB status distribution horizontal bars (sums to 100 percent)"; §4.2 asks
for a "compact horizontal status distribution bar mirroring the VOB tab chart". The
canonical model (§7.3) has **twelve** statuses.
**Interpretation:** the bar renders three groups — *In progress*, *Verified*, *Needs
attention* — with every individual status and its count present in the chart's relief
table. Two reasons, both binding: (1) the validated palette has six categorical colors and
cannot give twelve segments distinct, colorblind-safe, contrast-passing hues; (2) seven of
the eight terminal statuses all *mean bad*, and the color-formula rule is that a series
which means good/bad wears a status token, not a categorical one — so they legitimately
share one. Both the Overview bar and the VOB tab bar use the same grouping, so they mirror
each other as §4.2 requires. Per-status detail is never lost, only moved into the table.

### B16 — "Mark resolved" has no target status in the canonical model
§8.3 defines a `Mark resolved` action with a reason picker, but §17's VOB model has no
`resolved` status.
**Interpretation:** the action records the reason, appends a status-timeline entry, and
removes the row from the exception-driven worklist. It does **not** invent a `resolved`
status string, which would violate Rule 5 (enums declared exactly once, verbatim).

### B17 — VOB Queue has a Flag button that §8 never mentions
§8.3 enumerates exactly four row actions: Retry, Mark resolved, Escalate, Add note. No
Flag. But §12.5 says flags arrive "from the Flag this interaction button across
Appointments, Conversations, **VOB Queue**".
**Interpretation:** the button exists, and it is traceable to the §12.5 bullet rather than
to a §8 bullet — which satisfies Rule 1 ("every UI element traceable to a specific numbered
subsection"). It sits on each **call attempt** inside the §8.2 drawer, not on the
verification record, because §12.5 flags an *interaction*. Appointments behaves the same
way: an appointment with no originating interaction shows an explanation instead of a
disabled button, rather than writing a dangling flag reference.

### B18 — A clickable table row must not be `role="button"`
§5.2, §8.1, and §10.1 all open a detail drawer on row click. The obvious implementation —
`role="button"` + `tabIndex` on the `<tr>` — was written, shipped to a browser, and
**rejected on evidence**: those rows contain the §5.2 masked phone-reveal button, and an
interactive control nested inside another interactive control is invalid ARIA. A screen
reader would also announce the whole row as one button, flattening the cell semantics that
make a data table navigable.
**Interpretation:** the row keeps `onClick` as a **mouse convenience only**, with no role and
no tabindex. Keyboard and assistive-technology access comes from `RowOpenButton`, a real
`<button>` inside the first cell whose accessible name identifies the row. Cells holding
their own controls call `stopPropagation()`. Verified in a browser: 0 rows carry
`role="button"`, 12 expose a focusable opener, Enter opens the drawer, and clicking the
reveal button does not also open it.

### B19 — The location filter, role, and mode persist across a hard reload
§2.4: "A global location filter sits in the top bar and **persists across tabs**."

Client-side navigation preserves React state, so the filter appeared to satisfy this. A
hard reload silently reset it to "all locations" — and a filter that quietly resets while
someone is reading numbers for one clinic is worse than one that never existed. The demo
role and mode switchers had the same flaw, found the same way: a browser probe that
navigated with a full page load rather than a `<Link>`.

**Interpretation:** `SessionProvider` persists `{ role, mode, orgId, locationId }` to
`localStorage`, hydrating in an effect after mount so the first render still matches the
server's markup (reading storage during render throws a hydration mismatch). Every restored
field is validated against the canonical enums before being trusted, and a `locationId`
belonging to a different organization is discarded rather than silently scoping every query
to nothing.

**This is not a security boundary and must not be mistaken for one.** Role and mode are demo
state in this build; in a real deployment they arrive with the server session, and §2.2
requires the API to reject independently. Editing `localStorage` changes what this frontend
*renders*, never what a real API would *return*.

---

## E. Authentication (Clerk) — added after Milestone 1

### A13 — Clerk, not Supabase Auth. This contradicts `CLAUDE.md`.
The workspace's `CLAUDE.md` declares the stack's auth as **"Supabase Auth with RLS
policies"**. This dashboard now authenticates with **Clerk**. That is a real contradiction
and it is recorded here rather than resolved by silently editing a file outside this
folder's scope.

**Decision (CTO):** the contradiction is documented here; `CLAUDE.md` is updated separately
by the CTO. Nothing in `E:\Finova-Internal\AwaazLabs-V2\CLAUDE.md` was touched.

Both can be true: the client dashboard is a separate deployable product and may authenticate
with Clerk while the NestJS/Python platform continues to use Supabase Auth. If they are
later unified, it should be a deliberate decision, not an accident.

### A14 — Middleware was previously refused on security grounds. That reasoning no longer holds.
`next.config.mjs` used to state that this app "deliberately ships no middleware (it is the
surface behind CVE-2025-29927)". Clerk requires middleware, so that claim had to be
re-examined rather than quietly dropped.

CVE-2025-29927 (the `x-middleware-subrequest` authorization bypass) was **patched in Next.js
15.2.3**. This app runs **15.5.20** — verified against the installed package, not assumed.
The bypass is closed, and `clerkMiddleware()` is safe here.

**A second claim I made was simply wrong.** I predicted middleware would force all 25
prerendered pages to become dynamic, and warned about Vercel function cost. The build output
disproves it: pages remain `○ (Static)`; middleware executes per request at the edge; only
`/sign-in` is `ƒ (Dynamic)`. Corrected rather than left standing.

### A15 — Role comes from Clerk `publicMetadata`, and fails closed
`user.publicMetadata.role` is validated against the canonical `ROLES` union. An unknown
value, a missing value, or a malformed metadata object resolves to **`VIEWER`** — never to
`OWNER_ADMIN`. Failing closed on an admin's un-set metadata is a minor annoyance; failing
open is a breach.

`role` is deliberately **not** persisted to `localStorage` (unlike mode, org, and location).
Persisting it would let a user edit storage and change what the dashboard renders for them.
It is re-derived from the Clerk session on every load.

The demo role/mode switchers survive — the guide's Part F.3 requires every gated surface to
be exercisable — but behind `DEMO_CONTROLS_ENABLED = process.env.NODE_ENV !== 'production'`,
which is statically replaced at build time. The markup is removed by dead-code elimination in
a production build; it is not merely hidden with CSS. **A deployed build offers no way to
change your own role.**

None of this is the security boundary. §2.2: "Permission checks are server-side. The UI hides
what the role cannot access; the API independently rejects it." Authentication is enforced in
`src/middleware.ts`; a real backend must re-check authorization on every request.

### A16 — No `/sign-up` route, and that alone is not enough
§16.3: members are added by "invite by email with role assignment (Owner only)". There is no
`/sign-up` page. But omitting the route would not stop anyone reaching Clerk's **hosted**
sign-up page directly, so sign-up is also disabled in the Clerk dashboard. Two controls,
because the file-system one is not a control at all.

### A17 — CSP was widened to exactly Clerk's hosts, and nothing else was weakened
`connect-src 'self'` — the strongest control in the original policy, given the app made no
network calls — necessarily had to open. It now allows Clerk's frontend API and telemetry
endpoint, plus `img.clerk.com`, `challenges.cloudflare.com` (Turnstile bot protection), and
`worker-src blob:`. Each is a named host; there is no bare wildcard.

`frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, and `form-action 'self'`
are unchanged. Authentication widened the network surface; it did not weaken clickjacking,
plugin, or form-hijacking protection.

Clerk's anonymous telemetry endpoint is **explicitly allowed** rather than silently blocked
by CSP. A CSP violation is not consent management. Disable it honestly with
`<ClerkProvider telemetry={{ disabled: true }}>` if that is the intent.

### A18 — Routes moved into a `(dashboard)` route group
The root layout wrapped everything in `DashboardShell`, so `/sign-in` would have rendered
inside the dashboard chrome. All 25 routes moved to `src/app/(dashboard)/`. A route group adds
no URL segment: every path is unchanged, verified by the build output.

`GradeBreakdown` moved from `src/app/(dashboard)/quality/` to `src/components/quality/`. It is
imported by two different routes (§12.3 and §10.1), so it never belonged inside one route's
folder.

### A19 — `auth.protect()` answers 404; we redirect instead
Bare `auth.protect()` responds **404** to an anonymous request. Defensible — it does not
confirm the route exists — but it strands a signed-out user on a dead page. The middleware
now calls `redirectToSignIn({ returnBackUrl })`, so `/vob-queue?filter=needs-attention`
survives the round trip through login. Verified: every protected route returns `307` to
`/sign-in` with the deep link intact.

This requires `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`. Without it Clerk redirects to its
hosted Account Portal on a different domain — not the page we built.

### A20 — Access is restricted to one Clerk organization, and that is a *second* control
The dashboard is reachable only by members of the Clerk organization `healthcare-clinics`.

Worth being precise about what this buys, because it is easy to overstate: **sign-up is
disabled, so the Clerk instance is already the boundary.** Anyone who exists can sign in.
The organization check adds a second, explicit boundary that matters when the same Clerk
instance later hosts another application, or holds users who should not reach this
dashboard. It is not what keeps strangers out. Sign-up being off is.

Design decisions:

- **Slug, not id.** Clerk's development and production instances mint different organization
  ids for the same organization. A slug survives the promotion; an id does not.
- **Missing active organization is not a denial.** `orgSlug` is populated only when a session
  has an *active* organization, and a member who has never selected one arrives with
  `orgSlug === null`. `/select-organization` activates it for them silently — there is
  exactly one organization they could choose, so making them choose is friction, not a
  decision. A genuine non-member reaches the same page and is told plainly.
- **The denial screen names nothing.** No organization name, no member count, no reason
  beyond "you are not a member". A denial that reveals *which* organization exists hands an
  attacker the map.
- **Default when the env var is unset:** `healthcare-clinics`, not "deny all". Failing closed
  on a forgotten environment variable would brick a deployment; the slug is not a secret.

### A21 — The `redirect_url` parameter is an open-redirect vector
Middleware passes the original target through `?redirect_url=` so a deep link survives login.
Navigating to that value unchecked would make this app an open redirect: a link on our
trusted domain that bounces a freshly authenticated user onto an attacker's page. Phishing
kits are built on exactly this.

`safeRedirectPath()` in `src/shared/org-access.ts` accepts only same-origin paths. Verified
by probe — all nine cases pass, including the two that catch naïve implementations:

| Input | Result |
|---|---|
| `//evil.example` | `/` — scheme-relative is not a local path, however much it looks like one |
| `https://app.example.evil.com/x` | `/` — origin *prefix* is not origin *equality* |
| `/\evil.example` | `/` — some browsers normalise the backslash to a slash |
| `javascript:alert(1)` | `/` |

### A22 — There is one thing here I have not verified
The signed-out path is verified end to end: every protected route 307s to `/sign-in`, and the
org gate never shadows the auth gate. The **signed-in** paths — a member's organization being
auto-activated, and a non-member seeing the denial — need a real Clerk user in the
organization to exercise. They are implemented and typechecked, not browser-verified. Stated
rather than assumed.

---

## C. Skills used

| Skill | Source | Why |
|---|---|---|
| `dataviz` | bundled with Claude Code | Guide Part B item 3 (charts). Used to derive and **mechanically validate** the categorical palette, the sequential ramp, and the rejected ordinal ramp. Every colour in `THEME_NOTES.md` §3–§6 carries a validator result, not an opinion. |
| `.claude/skills/awaazlabs-theme/SKILL.md` | **written for this repo** | Guide Part B item 2. No design-system skill was installed and no marketplace access was assumed. Encodes the repo's real tokens, primitive inventory, and composition rules so every Phase 2 subagent loads theme discipline automatically instead of being told by hand. |

No third-party plugin was installed. Per Part B item 7, a hand-written skill encoding the
repo's actual tokens is preferred over an unverified third-party one.

---

## D. Open items (never silently dropped)

| # | Item | Status |
|---|---|---|
| D1 | §2.7 UI-locale i18n framework | ✅ **RESOLVED** — built, see B6 |
| D2 | 2 moderate `npm audit` findings (transitive `postcss` inside `next`) | ✅ **RESOLVED** — see A12. I was wrong that this was unfixable |
| D3 | Dark mode | ❌ deferred by explicit CTO decision. The spec never mentions it and no §-numbered screen requires it. Recorded as a deliberate choice, not an oversight |
| D4 | Server-side sort/filter (§5.2) | ⚠ Not implementable — this build has no server, by design ("Data is hardcoded only", guide Rule 4). Identical behavior runs client-side against the fixture. The `data-access.ts` seam is where a real API replaces it |

### A12 — The `npm audit` finding *was* fixable; my earlier analysis was wrong
I originally recorded the 2 moderate `postcss` advisories as unfixable, because
`npm audit fix` proposes downgrading to `next@9.3.3` and no `next` release pins a patched
`postcss`. That reasoning only holds if you accept npm's own remediation path.

An `overrides` block in `package.json` forces the transitive dependency directly:

```json
"overrides": { "postcss": "^8.5.16" }
```

Result: a single `postcss@8.5.16` resolves for the whole tree (Next's nested copy is
deduped), `npm audit` reports **0 vulnerabilities** for both production and dev
dependencies, and `next build` is unaffected. Verified, not assumed.

The lesson is recorded rather than quietly corrected: "the tool says it cannot be fixed" is
not the same as "it cannot be fixed."
