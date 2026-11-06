# Wavia Studio Complete Operations Design

**Date:** 2026-11-07

**Status:** Proposed for Hamzi approval

**Builds on:** Phase 13A–13G and the approved Wavia Theme B pilot

## Intent

Turn the Phase 13G pilot into the complete operating product: one coherent customer Studio for self-serve, enterprise, done-for-you and SDK users, plus a separately protected Wavia management area for internal staff. Every exposed route must be functional, permission-aware, responsive and visually composed; no browser-default screen may remain inside the production shell.

The immediate visual direction remains the approved dashboard pilot. Functional completeness, access boundaries and truthful states come first. Final decorative refinement happens only after all routes and role journeys work.

## Goals

- Apply the approved Studio shell and UI primitives to every current customer route.
- Make the sidebar collapse control unmistakable, remember the preference locally, reduce the operational type scale slightly and tighten spacing without reducing 44px targets.
- Serve self-serve owners, enterprise implementers, operators, SDK developers, viewers and compliance staff through least-privilege roles.
- Add a separate `/admin` area for Wavia staff rather than mixing cross-tenant tools into customer workspaces.
- Replace the current platform wildcard with explicit, durable platform roles and permissions.
- Keep FastAPI and PostgreSQL authoritative for identity, tenancy, permissions, entitlements and audit evidence.
- Make unavailable capabilities honest: hidden when irrelevant, disabled with a reason when discoverability matters, and never represented by fake data.
- Preserve all live-call, spend, deployment, billing and secret-handling gates.

## Non-goals

- No payment checkout, subscription charging or billing-role design before pricing is approved.
- No live provider qualification, live phone call, DID purchase, deployment or package publication.
- No silent tenant impersonation or unrestricted cross-tenant editing.
- No implementation of a planned screen merely because it appears in the old SCR inventory; it must have a real backend contract and release need.
- No final visual art-direction pass until functional rollout and role journeys pass.
- No new marketing website work.

## Anti-goals

- A half-redesigned application where raw HTML forms appear inside the finished shell.
- A growing list of narrowly named roles when permissions can express the difference.
- Client-side role checks acting as security boundaries.
- A single `platform_admin: {"*"}` identity with invisible cross-tenant power.
- Secret values, raw provider responses, unredacted sensitive transcripts or customer tokens in internal dashboards.
- “Support mode” that silently behaves as the customer.

## Current truth

- The Phase 13G shell, Agent Directory and Persona Editor are implemented and verified.
- Existing routes for onboarding, agent creation, knowledge, voice testing, channels, provider credentials, API keys, conversations, usage and audit are functionally implemented but many still use browser-default or inline styling.
- Existing customer roles are `tenant_admin`, `tenant_editor`, `tenant_viewer` and `compliance_admin`.
- FastAPI already enforces durable tenant membership; Studio navigation separately mirrors a subset of the backend permission matrix.
- `UserIdentity.is_platform_admin` exists. It becomes a wildcard `platform_admin` role and can cross tenant boundaries when an explicit tenant is supplied. There is no internal Studio surface, platform-role table, reason/expiry requirement or scoped support session.
- Membership and invitation APIs exist, but Studio has no `/settings/members` screen.
- The current sidebar points Settings to `/settings`, but that route does not exist. Test points back to `/agents` rather than a dedicated agent-selection workflow.
- Some historical SCR routes have no dedicated implementation. Current production truth is the implemented control-plane contract, not the inventory alone.

## Approaches considered

### 1. Mix staff controls into customer workspaces

Fastest initially, but it makes navigation confusing, increases the chance of cross-tenant mistakes and makes every customer component understand internal privileges. Rejected.

### 2. Separate `/admin` area in the same Studio deployment — selected

Customer and internal route groups share authentication, safe primitives and deployment operations while using separate layouts, navigation and permission dependencies. This gives a strong product boundary without prematurely operating a second frontend. Selected as the best current balance.

### 3. Separate internal application and deployment

Strongest infrastructure isolation, but duplicates authentication, release pipelines and shared UI before the internal workflows are stable. Defer until scale, compliance or team boundaries justify it. The server contracts designed now must allow this future extraction.

## Authorization architecture

### Rules

1. Backend permissions are authoritative. Frontend capability data controls presentation only.
2. Roles are durable permission bundles, not route names.
3. Every write repeats authorization server-side at the closest domain boundary.
4. Every tenant query remains tenant-scoped in the route, repository and RLS layers.
5. Cross-tenant platform access is explicit, reasoned, time-bounded where customer data is involved, and audited.
6. No role grants visibility of stored secret values.

### Customer roles

| Role | Purpose | Main capabilities |
| :--- | :--- | :--- |
| `tenant_admin` | Business owner or self-serve workspace administrator | All tenant configuration, members, keys, provider credentials, channels, agents, usage and audit allowed by entitlement. Last-admin protection remains. |
| `tenant_editor` | Staff member or enterprise implementer | Build, test, publish, knowledge and operational reads; no member administration, API keys, provider secrets or telephony-policy writes. |
| `tenant_developer` | SDK/integration developer | Web integration, scoped API-key lifecycle, provider capability metadata, technical diagnostics and agent/test reads; no member, compliance or business-policy administration. |
| `tenant_viewer` | Read-only business operator | Read permitted agents, knowledge state, conversations and usage; no session minting or writes. |
| `compliance_admin` | Compliance and review operator | Audit, permitted conversations, review decisions, legal hold/erasure workflows and compliance evidence; no agent or credential administration. |

No `tenant_owner` role is added yet. `tenant_admin` remains the durable owner-level role because billing, workspace transfer and account deletion are not implemented. A distinct owner role should be introduced only with those irreversible responsibilities.

### Platform staff roles

Platform roles live in a new durable platform-membership model rather than a boolean wildcard.

| Role | Purpose | Main capabilities |
| :--- | :--- | :--- |
| `platform_admin` | Wavia administration | Manage staff roles, tenant lifecycle metadata and entitlements; access remains permission-scoped rather than `*`. |
| `platform_support` | Customer support | Search tenants, inspect safe configuration/readiness and create an audited, expiring support session after entering a reason. Read-only by default. |
| `platform_operations` | Service operations | View provider, queue, telephony, runtime and quota health; acknowledge operational incidents; no customer secret or transcript access. |
| `platform_auditor` | Internal compliance/security | Cross-tenant audit and compliance evidence with redaction; no customer configuration writes. |

Emergency break-glass access is operational procedure, not a normal UI role. It requires strong identity controls and separate audit policy before implementation.

### Capability delivery

- A shared backend permission registry produces role permissions.
- Safe identity responses include role names and explicit capability strings.
- Studio components consume capability strings such as `agent:write` or `platform_tenant:read`; they do not infer access from names.
- Navigation items declare required capabilities and are generated for the active customer or platform context.
- Unknown roles and unknown capabilities fail closed.
- Human workspace roles and API-key delegated roles remain separate concepts. A `tenant_developer` human may manage eligible keys, while issued keys continue to receive only explicitly supported machine roles and scopes.
- Platform routes use a dedicated platform authorization dependency that does not require a fake tenant context. Tenant-scoped dependencies continue to require a selected durable membership or an explicit support grant.

## Product modes

Role and entitlement are separate from product mode:

- **Guided:** default for self-serve owners and nontechnical editors. Shows business intent and recommended routing.
- **Advanced:** available only when permission and entitlement both allow it. Shows provider, key and diagnostic controls.
- **Internal:** `/admin` only. Never appears as extra customer-workspace navigation.

The user can switch Guided/Advanced presentation only when eligible; the switch does not grant permissions.

## Customer Studio information architecture

### Global shell

- Wavia wordmark, workspace selector, task-based navigation, user/role context and sign-out.
- Explicit collapse button with familiar chevron/menu treatment, tooltip and `aria-expanded`.
- Collapse preference stored in local storage because it is non-sensitive; mobile uses an overlay drawer rather than a permanently narrow rail.
- Slightly smaller operational type and tighter vertical rhythm, while inputs and interactive targets remain at least 44px.
- Route-level breadcrumb or contextual header where the current object is not obvious.

### Customer routes to complete

| Area | Routes | Completion requirement |
| :--- | :--- | :--- |
| Entry | `/`, `/sign-in`, `/workspaces` | Branded authentication and workspace selection; invitation, empty, loading and error states. |
| Overview/setup | `/dashboard`, `/onboarding` | Real next actions, readiness and resumable setup; no decorative metrics. |
| Agents | `/agents`, `/agents/new`, `/agents/[id]/build`, `/agents/[id]/test` | Complete create→configure→validate→publish→test journey with role-aware actions. |
| Test entry | `/test` | Select a real eligible published agent, then enter its existing browser test route; never route ambiguously back to the agent directory. |
| Knowledge | `/knowledge` | Upload/FAQ lifecycle, processing/retry, preview, activation and agent binding. |
| Connect | `/channels`, `/channels/web`, `/channels/telephony` | Web integration instructions and honest telephony readiness/policy without carrier purchase. |
| Operate | `/conversations`, `/conversations/[callId]`, `/settings/usage`, `/settings/audit` | Filters, detail, transcript/intelligence/review states, quota and audit evidence. |
| Developer | `/developers/api-keys`, `/settings/providers` | One-time key reveal, revocation and credential metadata/status with advanced eligibility. |
| Workspace | `/settings`, `/settings/members` | Settings landing plus membership list, invitation, role change and removal with last-admin protection. |

`/settings`, `/settings/members` and `/test` are the only new customer routes required immediately. Settings and members repair existing navigation and expose an implemented backend contract; Test provides a truthful entry into the existing per-agent sandbox.

### Planned capabilities that remain gated

Dedicated agent routes for language/voice, provider chains, tools/MCP, extraction, per-agent telephony, compliance, review queues and live monitoring are added only after a contract audit confirms production backend support. Until then, existing consolidated controls remain accessible and the UI must not create dead navigation.

## Wavia management area

### Routes

| Route | Purpose | Default platform roles |
| :--- | :--- | :--- |
| `/admin` | Internal overview and actionable platform status | all platform roles, capability-filtered |
| `/admin/tenants` | Tenant directory with search, status and entitlement summary | admin, support, operations, auditor read scopes |
| `/admin/tenants/[tenantId]` | Safe tenant profile, readiness, usage and audit summary | capability-filtered |
| `/admin/operations` | Provider/runtime/queue/telephony health | admin, operations; support read subset |
| `/admin/audit` | Cross-tenant internal and customer-boundary audit | admin, auditor |
| `/admin/staff` | Platform staff role assignment and revocation | platform admin only |
| `/admin/support-sessions` | Request, inspect and terminate reasoned support sessions | admin and support |

### Support-access contract

- Support starts from the internal tenant detail, never by editing a tenant ID in a URL or header.
- User supplies a reason and selects a bounded read scope.
- Server creates a short-lived support grant with actor, tenant, reason, scope, issue/reference and expiry.
- A persistent banner identifies the tenant and expiry.
- Every access and mutation is audited against the Wavia actor; it never appears as the customer.
- Initial release is read-only. Any later write scope requires a separate confirmation and allowlist.
- Transcript/recording access is absent by default and requires compliance capability plus an additional audited reason.

### Data boundary

Internal views show safe metadata, readiness, redacted diagnostics and aggregate usage. They never return credential values, API-key plaintext, session tokens, full internal exception payloads or unredacted sensitive content by default.

## Backend changes

- Add `tenant_developer` to durable membership validation, invitations, permission tests and safe DTO schemas.
- Replace `users.is_platform_admin` authorization with durable platform-role assignments and a migration path for existing flagged users.
- Remove the `platform_admin: {"*"}` wildcard after all required platform capabilities are explicitly enumerated.
- Add platform permissions, platform-member repository methods and protected management routes.
- Add a separate platform identity context/dependency for non-tenant internal routes; never satisfy tenant requirements with an empty or synthetic tenant ID.
- Add audited support-grant storage with reason, tenant, scope, actor, creation, expiry and revocation.
- Return safe capability lists from identity/session resolution so Studio and FastAPI share one permission truth.
- Add bounded tenant-directory and platform-status queries; no unbounded cross-tenant list.
- Preserve explicit tenant context, RLS and last-admin protection.

## Frontend structure

- Keep server components responsible for authenticated reads and permission decisions.
- Split layouts into customer `(studio)` and internal `(admin)` route groups with distinct navigation.
- Replace route-local inline styling with shared tokens and focused primitives: page header, tabs, field groups, data table/list, status badge, notices, dialogs, empty/loading/error states and sticky action/status bars.
- Do not create a giant generic component library; extract only patterns used by multiple routes.
- Maintain ready, empty, loading, error, permission-blocked, entitlement-blocked and degraded states for each operational surface.
- Preserve existing action signatures and APIs unless the backend contract is intentionally extended by this design.

## Rollout phases

### Phase 13H — Customer access and shell completion

- Add `tenant_developer` and shared capability delivery.
- Make sidebar collapse explicit, persistent and responsive; tighten type/spacing.
- Complete public/workspace/dashboard/onboarding/agent-creation surfaces.
- Implement `/settings/members` against existing membership APIs.
- Verify all five tenant-role journeys and cross-tenant denial.

### Phase 13I — Customer operational surface completion

- Convert knowledge, test, channels, API keys, providers, conversations, usage and audit to the approved dashboard system.
- Remove route-local browser-default and inline styling.
- Verify all functional states and existing end-to-end journeys.

### Phase 13J — Platform management security foundation

- Add durable platform roles, explicit permission matrix, migration from the boolean flag, internal route group and safe tenant directory/detail.
- Add platform audit and staff management.
- Keep support sessions read-only and time-bounded.

### Phase 13K — Operations, support sessions and completion QA

- Complete internal operations health and support-session workflows.
- Run customer/platform multi-role security, browser, accessibility, responsive and offline regression suites.
- Perform the final visual consistency/polish pass across all completed routes.
- Stop for Hamzi's production review; deploy/live/spend remain separate approvals.

Each phase must end in a small verified commit set and update the execution tracker and progress ledger. No phase begins its successor until its own tests and integrity checks pass.

## Verification strategy

- Backend permission unit tests for every tenant/platform role and capability.
- Route matrix tests for unauthenticated, wrong-role, wrong-tenant, unknown-role and expired support-grant cases.
- Disposable PostgreSQL tests for platform-role migration, RLS, membership changes, last-admin protection and support-grant audit.
- Studio unit tests for capability-filtered navigation/actions and all component states.
- Playwright journeys for self-serve admin, editor, developer, viewer, compliance, platform support, operations, auditor and platform admin.
- Cross-tenant tampering tests remain mandatory.
- Browser QA at desktop, 390px and 320px, plus keyboard, reduced motion, Axe and overflow checks.
- Final release qualification records Safari, physical device, screen-reader, forced-colors, Lighthouse and Core Web Vitals separately.

## Human and safety gates

- No raw API/provider secrets are read, printed, stored in docs or committed.
- No payment, deploy, package publish, live provider call or live phone call occurs in these phases.
- Platform staff bootstrap and break-glass identity policy require separate operational approval before production.
- Any support-session write capability requires a later explicit approval; the initial implementation is read-only.
- Final visual approval happens after functional completion, as requested.

## Success criteria

1. No reachable production Studio route displays browser-default composition.
2. A self-serve admin can complete the offline create→configure→knowledge→test→publish→connect journey without code.
3. Enterprise editors, developers, viewers and compliance users see only appropriate navigation and actions.
4. Wavia staff operate from `/admin`, never from hidden customer controls.
5. Cross-tenant access is permissioned, reasoned where customer data is involved, bounded and audited.
6. Backend and frontend consume one capability truth and fail closed on unknown access.
7. All unit, integration, browser, accessibility, responsive, build, lint, type and security gates pass before final visual review.
