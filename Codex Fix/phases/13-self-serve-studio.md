# Phase 13 — Self-Serve Wavia Studio Design

**Status:** APPROVED FOR PLANNING — IMPLEMENTATION NOT STARTED

**Decision date:** 2026-10-29

**Goal:** Let a nontechnical customer create, test, publish, connect, and operate a Wavia web or calling agent without editing code, while giving enterprise and SDK customers access to the same tenant-safe control-plane contracts.

**Depends on:** Phases 05–12.

**Implementation plan:** [`13-implementation-plan.md`](13-implementation-plan.md)

## Approved product and architecture decisions

Hamzi approved the recommended production route:

1. Build a new standalone `studio/` application with Next.js 16 Active LTS, App Router, strict TypeScript, and a server-side backend-for-frontend/data-access layer.
2. Keep FastAPI as the authoritative business backend. The Studio server may authenticate, authorize, validate, filter, and proxy; it must not duplicate Wavia domain logic.
3. Preserve `examples/web-client/index.html` as an engineering/demo console. It is not the customer Studio and must not be expanded into one.
4. Keep OAuth/OIDC access and refresh tokens server-side. The browser receives only a secure, HTTP-only session cookie and safe data-transfer objects.
5. Resolve organizations, roles, and permissions from durable server-side memberships. Never trust tenant, role, or scope claims supplied by the browser.
6. Use one Studio for all three deployment models:
   - self-serve customers use guided defaults;
   - done-for-you and enterprise customers use advanced/admin controls;
   - packaged SDK customers manage keys, usage, agents, and integration instructions.
7. Default to recommended automatic provider routing. Provider chains, credential tiers, MCP, extraction schemas, and telephony policies live behind Advanced mode and role checks.
8. Phase 13 implements entitlement and usage visibility, not payment checkout, subscription charging, DID purchasing, deployment, or live calls.
9. Visual redesign is deliberately deferred. Hamzi will provide visual references before the visual implementation pass. Functional foundations must remain themeable and accessible in the meantime.

## Why the existing interfaces are not the foundation

`examples/web-client/index.html` is a useful 2,947-line diagnostic surface with raw provider selectors, endpoint checks, UUID inputs, and hard-coded demo tenant/agent values. It remains valuable for engineers but is unsafe and too implementation-oriented for customer onboarding.

The legacy Next.js dashboards demonstrate useful navigation and workflow ideas. They are references only: their auth, mock data, route coverage, dependencies, and product assumptions do not define the new Studio.

## Users and modes

### Guided mode — default

For business owners and operators. It exposes intent, business facts, voice, knowledge, testing, channels, and results. Wavia chooses eligible provider chains and safe defaults.

### Advanced mode

For tenant admins, enterprise implementers, and SDK developers. It exposes provider routing, credential metadata, API keys, schemas, tools, MCP configuration, telephony policy, version history, and diagnostic evidence.

### Platform administration

For Wavia operators only. It can inspect readiness and audit evidence across tenants but cannot silently enter a tenant or expose secret values. Cross-tenant access must be explicit, permission-checked, and auditable.

## Primary customer journey

The Studio optimizes for “first working agent,” not for completing a settings form.

1. **Sign in or accept an invitation.**
2. **Create or select a workspace.** The server returns only memberships belonging to the authenticated identity.
3. **Choose an outcome.** Initial templates are customer support, lead qualification, appointment/intake, and custom.
4. **Describe the business.** Collect business name, use case, supported languages, operating region/time zone, escalation contact, and compliance/recording choices.
5. **Shape the agent.** Configure name, behavior, boundaries, language, and voice. Recommended provider routing stays automatic.
6. **Add trusted knowledge.** Reuse the Phase 10 knowledge lifecycle: upload supported files or FAQs, watch honest ingestion states, preview citations, activate a revision, and bind it to the draft.
7. **Test in the browser.** Use the packaged TypeScript realtime SDK. Clearly label offline/mock versus live, show mic/connection state, transcripts, latency, interruption, usage, and typed failures.
8. **Review readiness.** Present a deterministic checklist covering validation, knowledge, consent, quota, provider credentials, and selected channel.
9. **Publish an immutable version.** Autosaved drafts never silently change active sessions. Restoring an older version creates a new draft; it never mutates historical evidence.
10. **Connect a channel.** Web integration is available first. Telephony shows readiness and configuration; number purchasing, carrier provisioning, and live calls remain gated.
11. **Operate.** Show conversations, transcripts, consented recordings, extracted results, review queues, usage, health, and failures without inventing unavailable data.

Onboarding progress is resumable. A user may leave at any step without losing a valid draft. Completion percentages must be derived from completed requirements, not decorative estimates.

## Information architecture

| Route | Purpose | Default roles |
|---|---|---|
| `/sign-in` | OIDC sign-in and invitation handoff | public |
| `/workspaces` | create/select a permitted workspace | authenticated |
| `/onboarding` | resumable business and first-agent setup | admin, editor |
| `/agents` | list agents and visible state | all tenant roles |
| `/agents/new` | template-driven creation | admin, editor |
| `/agents/[agentId]/build` | guided builder and readiness | admin, editor |
| `/agents/[agentId]/test` | browser voice test | admin, editor |
| `/agents/[agentId]/versions` | immutable versions and restore-to-draft | all; write actions admin/editor |
| `/knowledge` | knowledge bases and ingestion | all; write actions admin/editor |
| `/conversations` | tenant-scoped conversation/call history | all permitted roles |
| `/conversations/[callId]` | transcript, recording status, extraction, review | all permitted roles |
| `/channels/web` | SDK/embed integration instructions | admin, editor |
| `/channels/telephony` | carrier readiness and policy, no purchase | admin |
| `/developers/api-keys` | create/list/revoke tenant API keys | admin |
| `/settings/providers` | credential status and advanced routing | admin |
| `/settings/members` | memberships and invitations | admin |
| `/settings/usage` | entitlement, quota, and usage evidence | admin, viewer |
| `/settings/audit` | audit history | tenant admin, compliance admin |

Navigation is task-based: Build, Test, Connect, Operate, Settings. Raw endpoint matrices and internal service health remain in the engineering console.

## Security architecture

### Authentication

- Use an external OIDC provider through Authorization Code with PKCE.
- Use a maintained authentication library or standards-compliant OIDC client; do not write OAuth cryptography.
- Keep access/refresh tokens in the Studio server session store or encrypted HTTP-only cookies as supported by the selected library.
- Cookies use `Secure` in protected environments, `HttpOnly`, `SameSite=Lax`, a narrow path, rotation, and finite lifetime.
- Never store access tokens, refresh tokens, API keys, or provider credentials in local storage, session storage, URLs, client logs, analytics, or React state.

### Identity and tenancy

Add a provider-neutral external identity mapping:

- `users` stores a safe user record; local passwords are not used by Studio.
- `external_identities` maps `(issuer, subject)` to one user.
- `memberships` remains the source of truth for tenant role.
- `invitations` stores hashed, expiring, single-use invitation tokens.
- `resolve_identity_context` validates the OIDC token and resolves the external identity.
- `resolve_auth_context` requires a selected tenant for tenant routes and derives roles from durable membership.
- `X-Tenant-Id` is accepted only as a requested workspace identifier; it never grants access.

The Studio BFF sends the authenticated access token and selected tenant to FastAPI. FastAPI performs the final membership and permission check close to the data.

### Browser/backend boundary

- Server Components call the server-only data-access layer directly.
- Browser mutations use narrow route handlers or server actions that repeat authorization and schema validation.
- Route handlers return safe DTOs, never raw provider responses, internal exceptions, credentials, or cross-tenant identifiers.
- The browser connects directly only to the realtime WebSocket using a short-lived, one-use voice-session token minted for the selected tenant, agent, origin, and published version.
- Uploads remain bounded by the Phase 10 file contract.

### Auditing and privacy

Audit sign-in outcomes, workspace creation, membership changes, invitation lifecycle, API-key lifecycle, credential metadata changes, publish/restore actions, telephony policy changes, and recording access. Never audit secret values or full tokens.

Recording visibility respects Phase 11 consent, retention, residency, and deletion state. Missing or deleted artifacts are shown honestly.

## Control-plane contracts required before UI completion

### Identity and workspaces

| Method | Endpoint | Contract |
|---|---|---|
| GET | `/v1/me` | safe identity plus permitted workspace summaries |
| POST | `/v1/organizations` | atomically create tenant and owner membership |
| GET | `/v1/organizations/{tenant_id}/members` | tenant-scoped membership list |
| POST | `/v1/organizations/{tenant_id}/invitations` | create one-time invitation; token returned once |
| POST | `/v1/invitations/accept` | consume invitation for authenticated identity |
| PATCH | `/v1/organizations/{tenant_id}/members/{user_id}` | change allowed role |
| DELETE | `/v1/organizations/{tenant_id}/members/{user_id}` | revoke membership with last-admin protection |

### Onboarding and entitlements

| Method | Endpoint | Contract |
|---|---|---|
| GET/PATCH | `/v1/onboarding` | durable, tenant-scoped progress and business profile |
| GET | `/v1/entitlements` | capabilities and numeric limits; no pricing estimate |

### Agents and capabilities

| Method | Endpoint | Contract |
|---|---|---|
| GET | `/v1/catalog/providers` | safe provider/model/language/voice capability metadata and readiness |
| GET | `/v1/agents/templates` | source-controlled guided templates |
| PATCH | `/v1/agents/{agent_id}/autosave` | optimistic draft revision; stale writes fail |
| POST | `/v1/agents/{agent_id}/validate` | structured readiness issues |
| POST | `/v1/agents/{agent_id}/versions/{version}/restore` | copy snapshot to a new draft revision |

### Credentials and SDK access

| Method | Endpoint | Contract |
|---|---|---|
| GET/POST | `/v1/api-keys` | list metadata/create key; plaintext returned once |
| DELETE | `/v1/api-keys/{key_id}` | revoke, never recover plaintext |
| GET | `/v1/provider-credentials` | provider, tier, reference, status, timestamps only |
| POST | `/v1/provider-credentials` | accept secret over protected request; response omits value |
| DELETE | `/v1/provider-credentials/{credential_id}` | revoke and invalidate caches |

### Operations and channels

| Method | Endpoint | Contract |
|---|---|---|
| GET | `/v1/conversations` | paginated/filterable call summaries |
| GET | `/v1/conversations/{call_id}` | safe call detail, transcript, usage, recording state |
| GET | `/v1/conversations/{call_id}/intelligence` | extraction/summary/review state |
| GET | `/v1/reviews` | tenant review queue |
| GET/PUT | `/v1/telephony/settings` | readiness and allowed policy only |
| GET | `/v1/usage` | durable totals, quota, and concurrency |
| GET | `/v1/audit` | tenant-scoped audit events |

Every list endpoint uses bounded pagination, deterministic sorting, and tenant filtering at repository and RLS levels.

## Draft, publish, and restore semantics

Each agent draft gains a monotonically increasing `draft_revision`.

- A successful autosave includes `expected_revision` and returns the next revision.
- A stale save returns HTTP 409 with the current revision and no partial merge.
- Validation returns stable issue codes, severity, path, and safe message.
- Publish validates the exact draft revision and produces the next immutable version.
- A published version remains active until another version is successfully published.
- Restore copies a historical snapshot into a new draft revision. The user reviews and publishes it normally.
- An active voice session remains pinned to its original published version.

## Provider experience

Guided users choose language, region, voice character, and quality/cost preference only where backed by real policy. Wavia resolves an eligible route from the source-controlled provider catalog and tenant entitlement.

Advanced users can inspect and edit provider chains subject to:

- catalog capabilities;
- credential tier and readiness;
- language/model compatibility;
- minimum usable fallback requirements;
- production no-mock policy;
- transparent typed failures.

The Studio never labels a provider “connected” merely because a credential record exists. Readiness distinguishes configured, verified-offline, qualified-live, degraded, and unavailable.

## Telephony boundary

Phase 13 provides:

- Telnyx readiness checklist;
- inbound/outbound policy visibility;
- allowed-origin/destination policy metadata;
- agent/channel binding;
- safe instructions for carrier configuration;
- controlled single-call UI only after H15 explicitly authorizes destination, budget, and live testing.

Phase 13 does not provide:

- DID purchasing or automatic carrier account creation;
- bulk campaigns or predictive dialing;
- hidden live qualification;
- provider credentials in browser state;
- a claim that telephony is ready before Phase 12 readiness evidence passes.

## Usage and entitlement boundary

`tenant_entitlements` is a durable capability/limit record, not a billing system. It controls:

- maximum agents;
- maximum concurrent sessions;
- knowledge/storage limits;
- API-key allowance;
- telephony availability;
- advanced provider/BYOK availability;
- permitted retention options.

Phase 13 shows current usage and enforced limits. It does not calculate prices, collect payment details, charge cards, or claim savings. Payment and subscription integration require a separately approved pricing and billing phase.

## Error and empty-state contract

The UI must distinguish:

- not configured;
- processing;
- ready;
- degraded;
- blocked by permission;
- blocked by entitlement;
- failed with retry available;
- failed requiring an administrator;
- deleted/expired by retention;
- unavailable because live qualification has not occurred.

Errors carry a safe correlation/request ID. No UI converts a failure into fake content or success.

## Accessibility and responsive requirements

- WCAG 2.2 AA target for keyboard navigation, focus visibility, names, contrast, forms, errors, and status announcements.
- Desktop, tablet, and mobile layouts; no horizontal overflow at 390 px.
- Realtime transcript and latency updates use restrained live regions.
- Reduced-motion preference is honored.
- Long IDs and diagnostic payloads are available through deliberate copy/reveal controls, not primary layout.
- No card-inside-card clutter, generic AI gradients, or decorative metrics.

The final visual system will be designed from Hamzi's references before Phase 13G. No visual direction is inferred now.

## Subphases and release gates

### 13A — Identity and Studio API foundations

Durable external identity/membership resolution, workspace/invitation APIs, entitlement/onboarding models, capability catalog, API-key/credential metadata APIs, conversation queries, optimistic agent contracts.

**Gate:** Cross-tenant, stale-write, invitation replay, last-admin, and secret-redaction tests pass against disposable PostgreSQL.

### 13B — Studio shell and secure BFF

Create `studio/`, server-only OIDC session/DAL, safe DTO client, route protection, workspace selection, role-aware shell, and test harness.

**Gate:** No token reaches the client bundle/storage; two-tenant authorization journeys pass.

### 13C — Guided agent builder

Templates, onboarding, draft autosave/conflict recovery, validation, readiness, publish, version history, and restore-to-draft.

**Gate:** A nontechnical fixture user creates and publishes a valid mock-backed agent without raw IDs or environment editing.

### 13D — Knowledge and browser voice test

Production UI for Phase 10 knowledge lifecycle plus TypeScript realtime SDK browser testing with honest environment, transcript, latency, interruption, quota, and failure states.

**Gate:** Offline create→knowledge→test evidence passes; no live provider or call occurs.

### 13E — Channels, credentials, and developer access

Web integration instructions, one-time API-key display, credential status/revocation, advanced routing, and telephony readiness.

**Gate:** Secret/token scans and role tests pass; carrier actions remain disabled.

### 13F — Conversations and operations

Conversation history/detail, consented recording state/access, intelligence/review, usage, audit evidence, and honest empty/degraded states.

**Gate:** Tenant/RLS isolation, retention/deletion, pagination, and review workflow tests pass.

### 13G — Approved visual system and production QA

After Hamzi supplies inspiration: design brief, visual system, responsive/a11y polish, Playwright screenshot critique, full browser journeys, build/type/lint/security verification.

**Gate:** Hamzi approves the critical screenshots; offline full suite passes; no deploy/publish/live call occurs.

## Human gates

Resolved:

- Production architecture: standalone Next.js Studio with thin BFF/DAL.
- Product model: one Studio with guided and advanced modes.
- Billing boundary: usage/entitlements only, no charging.
- Telephony boundary: readiness/configuration only until H15.
- Existing engineering console remains separate.

Still required:

- Before 13B auth integration: Hamzi chooses/provisions the external OIDC provider and supplies only environment variable names/status, never secret values in chat or Git.
- Before 13G: Hamzi supplies visual inspiration and approves the resulting design brief.
- Before any live carrier/provider action, deploy, payment, package publish, or spend: separate H15 approval.

## Phase exit criteria

Phase 13 is complete only when:

1. A new invited or self-serve user can enter an authorized workspace and cannot access another tenant by changing client state or headers.
2. A guided user can create, configure, test offline, validate, publish, and integrate a web agent without code or environment editing.
3. Draft conflicts are explicit and published versions are immutable.
4. Knowledge, provider, telephony, recording, extraction, review, and usage states are truthful.
5. Credentials and tokens never appear in client storage, URLs, logs, screenshots, error payloads, or committed files.
6. Tenant isolation passes application, repository, and RLS tests.
7. Desktop/mobile Playwright journeys, accessibility checks, production build, typecheck, lint, and offline regressions pass.
8. Hamzi approves the final critical screenshots.
9. No payment, deployment, package publication, live provider request, or live phone call was performed without separate approval.
