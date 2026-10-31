# Phase 13 Self-Serve Wavia Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure, tenant-isolated Wavia Studio in which nontechnical users can create, test, publish, connect, and operate web and calling agents.

**Architecture:** A new Next.js 16 App Router application provides the customer interface and a thin server-only BFF/DAL. FastAPI remains authoritative for identity-to-membership resolution, agents, knowledge, credentials, usage, calls, and audit data. Browser realtime audio uses the existing TypeScript SDK with a short-lived one-use session token; OAuth tokens and secrets never enter browser storage.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, PostgreSQL/pgvector with RLS, Redis, Next.js 16 Active LTS, React 19, strict TypeScript, Zod, existing Wavia TypeScript realtime SDK, Vitest/Testing Library, Playwright, axe-core.

**Spec:** `Codex Fix/phases/13-self-serve-studio.md`

## Global Constraints

- Work only on `wavia-fixv1`; never push `main` or edit `.github/workflows`.
- Create a rollback commit before the first risky multi-file implementation change.
- Never read or modify `API KEYS VOICESDK - hamzicodes@gmai.txt` or any raw API-key file.
- Never print, persist in plans/logs, or commit secret values. Environment inspection is limited to variable names.
- Keep `legacy_codebases/` and `docs/blueprint/` read-only.
- Keep `examples/web-client/index.html` as the engineering console; do not turn it into Studio.
- Use Next.js 16 Active LTS on the latest stable 16.x security patch available when Task 7 starts; never use `canary`. Lock exact versions in `studio/package-lock.json`.
- Use an external OIDC Authorization Code + PKCE flow. Do not implement password authentication or OAuth cryptography.
- OIDC access/refresh tokens and provider credentials remain server-side; never use browser local/session storage for authentication.
- FastAPI derives tenant role from durable membership. Browser headers, cookies, form values, and token tenant/role claims cannot grant membership.
- Use server-only DAL modules and safe DTOs. FastAPI remains the source of business truth.
- No payment collection, billing estimate, DID purchase, carrier provisioning, live provider request, live phone call, deployment, or package publication.
- Set `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_DB_TESTS=0`, and `RUN_LIVE_REDIS_TESTS=0` for ordinary evidence.
- Use disposable PostgreSQL/Redis only for explicitly gated integration commands; remove containers and volumes afterward.
- Follow TDD: focused failing test, minimal implementation, focused pass, related regression pass, diff/security review.
- Stop after each subphase gate. Do not commit or push that subphase until Hamzi gives the required confirmation.
- Do not begin Phase 14.

## Review Focus

- A valid OIDC subject requesting an unowned `X-Tenant-Id` must receive 403, and changing browser cookies/headers must not alter server membership; Tasks 2, 7, and 8 test this.
- Invitation tokens must be hashed, expiring, single-use, and unable to remove or demote the final tenant admin; Tasks 1–3 test this.
- Two tabs editing the same draft must not silently overwrite each other; Tasks 5 and 9 test revision conflicts and recovery.
- Tokens, provider secrets, and newly created API-key plaintext must not reach logs, URLs, client storage, serialized Server Component props, or later API reads; Tasks 6, 7, and 12 test this.
- Missing/deleted recordings, unqualified telephony, unavailable providers, exhausted entitlement, and failed ingestion must render honest states rather than fabricated success; Tasks 4, 11–13 test this.

---

## Locked file structure

### Control plane

- `infra/db/migrations/030_studio_control_plane.sql` — external identities, invitations, onboarding profiles, entitlements, draft revisions, and required RLS.
- `control_plane/studio/models.py` — public Studio domain/DTO models.
- `control_plane/studio/repository.py` — repository protocol and in-memory test implementation.
- `control_plane/studio/pg_repository.py` — PostgreSQL implementation with tenant transactions.
- `control_plane/studio/dependencies.py` — identity and membership resolution.
- `control_plane/routes/identity.py` — `/v1/me`, organizations, memberships, invitations.
- `control_plane/routes/studio.py` — onboarding, entitlements, templates, provider catalog.
- `control_plane/routes/api_keys.py` — tenant API-key management HTTP surface.
- `control_plane/routes/provider_credentials.py` — credential metadata/create/revoke HTTP surface.
- `control_plane/routes/conversations.py` — paginated call, intelligence, and review reads.
- Existing `control_plane/routes/agents.py` — revision-aware autosave, validate, restore.
- Existing `control_plane/routes/telephony.py` — safe settings/readiness only.

### Studio

- `studio/src/app/` — App Router pages, layouts, route handlers, loading/error boundaries.
- `studio/src/auth/` — server-only OIDC/session adapter and selected-workspace cookie.
- `studio/src/data/` — generated API types, server-only control-plane client, DTO mappings.
- `studio/src/features/` — vertical feature folders: workspaces, onboarding, agents, knowledge, voice-test, channels, credentials, conversations, usage, audit.
- `studio/src/components/` — shared accessible primitives only.
- `studio/src/styles/` — tokens and approved visual system; no feature business logic.
- `studio/tests/` — unit/component tests.
- `studio/e2e/` — Playwright multi-role journeys and screenshots.

## Phase 13A — Identity and Studio API foundations

### Task 1: Durable Studio identity schema and repositories

**Files:**
- Create: `infra/db/migrations/030_studio_control_plane.sql`
- Create: `control_plane/studio/__init__.py`
- Create: `control_plane/studio/models.py`
- Create: `control_plane/studio/repository.py`
- Create: `control_plane/studio/pg_repository.py`
- Create: `tests/studio/test_studio_repository.py`
- Create: `tests/db/test_phase13_studio_migration.py`

**Interfaces:**
- Produces: `IdentityContext(subject: str, issuer: str, email: str | None)`.
- Produces: `WorkspaceMembership(user_id, tenant_id, tenant_name, role)`.
- Produces: `OnboardingProfile` and `TenantEntitlements` safe models.
- Produces: `StudioRepository.resolve_identity(identity) -> UserIdentity`.
- Produces: `StudioRepository.list_memberships(user_id) -> tuple[WorkspaceMembership, ...]`.
- Produces: atomic organization, invitation, membership, onboarding, and entitlement methods.

- [x] **Step 1: Write failing repository tests**

Add tests named `test_external_identity_is_unique_by_issuer_and_subject`, `test_create_workspace_atomically_adds_owner`, `test_invitation_token_is_hashed_single_use_and_expiring`, `test_last_admin_cannot_be_removed_or_demoted`, `test_onboarding_and_entitlements_are_tenant_scoped`, and `test_repository_does_not_return_secret_material`.

- [x] **Step 2: Run the focused tests and confirm they fail**

Run: `py -3.12 -m pytest tests/studio/test_studio_repository.py tests/db/test_phase13_studio_migration.py -q`

Expected: collection/import failures for missing Studio models, repository, and migration contracts.

- [x] **Step 3: Implement the migration**

Add `external_identities`, `workspace_invitations`, `tenant_onboarding_profiles`, and `tenant_entitlements`; add `draft_revision` to the durable agent draft representation. Use unique constraints, expiry/use timestamps, indexes, RLS, forced RLS, and the canonical `ucve_app` policies. Do not add local password login.

- [x] **Step 4: Implement repository contracts**

Keep invitation plaintext ephemeral: repository storage accepts only a token hash; service code returns plaintext once. Enforce last-admin invariants inside the transaction.

- [x] **Step 5: Run focused and migration-integrity tests**

Run: `py -3.12 -m pytest tests/studio/test_studio_repository.py tests/db/test_phase13_studio_migration.py tests/db/test_phase09_database.py -q`

Expected: all pass.

### Task 2: OIDC identity and durable membership authorization

**Files:**
- Create: `control_plane/studio/dependencies.py`
- Modify: `control_plane/auth/oidc_hook.py`
- Modify: `control_plane/auth/dependencies.py`
- Modify: `control_plane/auth/context.py`
- Modify: `control_plane/app.py`
- Create: `tests/auth/test_studio_identity.py`
- Modify: `tests/auth/test_route_matrix.py`

**Interfaces:**
- Produces: `resolve_identity_context(request, authorization) -> IdentityContext`.
- Produces: `resolve_auth_context(...) -> AuthContext` whose roles come from `StudioRepository` membership.
- Requires: tenant-scoped routes receive `X-Tenant-Id` or an equivalent explicit selected-tenant input.
- Preserves: API-key authentication and existing RBAC permission semantics.

- [x] **Step 1: Write failing authorization tests**

Cover valid membership, unknown subject, unowned tenant, tampered role header, conflicting token tenant/role claims, platform-admin explicit access, API-key compatibility, and protected-environment OIDC stub refusal.

- [x] **Step 2: Verify focused failures**

Run: `py -3.12 -m pytest tests/auth/test_studio_identity.py tests/auth/test_route_matrix.py -q`

- [x] **Step 3: Separate identity authentication from tenant authorization**

OIDC validation returns subject/issuer/email only. Resolve the selected tenant and role from the repository. Ignore OIDC tenant/role claims for authorization.

- [x] **Step 4: Run auth regressions**

Run: `py -3.12 -m pytest tests/auth tests/security/test_provider_credentials.py -q`

Expected: all pass with API-key flows preserved.

### Task 3: Workspace, invitation, onboarding, and entitlement APIs

**Files:**
- Create: `control_plane/routes/identity.py`
- Create: `control_plane/routes/studio.py`
- Modify: `control_plane/app.py`
- Create: `tests/studio/test_identity_api.py`
- Create: `tests/studio/test_onboarding_api.py`

**Interfaces:**
- Produces: endpoints from the design's Identity/workspaces and Onboarding/entitlements matrices.
- Produces: bounded safe DTOs; invitation plaintext is returned only from create and never list/read.
- Produces: deterministic onboarding requirement codes used by the frontend readiness checklist.

- [x] **Step 1: Write failing API tests**

Cover first-workspace creation, membership listing, invite create/accept/replay/expiry, role change, last-admin protection, tenant mismatch, onboarding resume, and entitlement enforcement.

- [x] **Step 2: Verify failures**

Run: `py -3.12 -m pytest tests/studio/test_identity_api.py tests/studio/test_onboarding_api.py -q`

- [x] **Step 3: Implement narrow routes and DTOs**

Register routers under `/v1`. Apply permissions at the route and repository boundaries. Return correlation IDs through existing middleware.

- [x] **Step 4: Run focused tests**

Run: `py -3.12 -m pytest tests/studio/test_identity_api.py tests/studio/test_onboarding_api.py tests/auth/test_route_matrix.py -q`

### Task 4: Provider/template catalog and operational read APIs

**Files:**
- Modify: `control_plane/routes/studio.py`
- Create: `control_plane/routes/conversations.py`
- Modify: `control_plane/routes/telephony.py`
- Modify: `control_plane/app.py`
- Create: `tests/studio/test_catalog_api.py`
- Create: `tests/studio/test_conversations_api.py`
- Create: `tests/studio/test_telephony_settings_api.py`

**Interfaces:**
- Produces: `GET /v1/catalog/providers` and `GET /v1/agents/templates`.
- Produces: cursor-based `GET /v1/conversations`, call detail, intelligence, and review DTOs.
- Produces: `GET/PUT /v1/telephony/settings` with readiness/policy metadata and no carrier action.

- [x] **Step 1: Write failing catalog/operations tests**

Test capability filtering, no secret/provider-internal fields, deterministic pagination, cross-tenant denial, deleted/expired recording states, unavailable intelligence, and telephony readiness without live action.

- [x] **Step 2: Verify failures**

Run: `py -3.12 -m pytest tests/studio/test_catalog_api.py tests/studio/test_conversations_api.py tests/studio/test_telephony_settings_api.py -q`

- [x] **Step 3: Implement safe adapters over existing domains**

Reuse `DEFAULT_PROVIDER_CATALOG`, source-controlled templates, Phase 11 repositories, and Phase 12 readiness services. Do not duplicate provider, post-call, or carrier state.

- [x] **Step 4: Run focused and related regression tests**

Run: `py -3.12 -m pytest tests/studio/test_catalog_api.py tests/studio/test_conversations_api.py tests/studio/test_telephony_settings_api.py tests/post_call tests/telephony/test_trunk_readiness.py -q`

### Task 5: Revision-safe agent editing and version restore

**Files:**
- Modify: `control_plane/agents/models/agent_config.py`
- Modify: `control_plane/agents/repo.py`
- Modify: `control_plane/agents/pg_repo.py`
- Modify: `control_plane/routes/agents.py`
- Modify: `tests/agents/test_session_plan_compiler.py`
- Create: `tests/studio/test_agent_builder_api.py`

**Interfaces:**
- Produces: `AutosavePatchBody.expected_revision: int`.
- Produces: `POST /v1/agents/{agent_id}/validate` with stable issue DTOs.
- Produces: `POST /v1/agents/{agent_id}/versions/{version}/restore`.
- Produces: HTTP 409 on stale autosave or publish revision with no mutation.

- [x] **Step 1: Write failing concurrency and restore tests**

Test two-editor stale save, exact-revision publish, structured validation, immutable old version, restore-to-new-draft, and active session pin stability.

- [x] **Step 2: Verify failures**

Run: `py -3.12 -m pytest tests/studio/test_agent_builder_api.py tests/agents/test_session_plan_compiler.py -q`

- [x] **Step 3: Implement revision compare-and-swap**

Increment draft revision only on committed mutation. Restore copies a snapshot into the draft and never rewrites a published row.

- [x] **Step 4: Run focused tests**

Run: `py -3.12 -m pytest tests/studio/test_agent_builder_api.py tests/agents tests/e2e/test_published_agent_runtime.py -q`

### Task 6: API-key and provider-credential management APIs

**Files:**
- Create: `control_plane/routes/api_keys.py`
- Create: `control_plane/routes/provider_credentials.py`
- Modify: `control_plane/app.py`
- Create: `tests/studio/test_api_key_management.py`
- Create: `tests/studio/test_provider_credential_management.py`

**Interfaces:**
- Produces: endpoints from the design's Credentials/SDK matrix.
- Requires: created API-key plaintext appears once; all later representations expose prefix/metadata only.
- Requires: provider credential responses and audit events omit secret values.

- [x] **Step 1: Write failing lifecycle/redaction tests**

Cover role enforcement, quota, one-time plaintext, list/revoke, expired/revoked verification, credential create/status/revoke, cache invalidation, and recursive secret-pattern scans.

- [x] **Step 2: Verify failures**

Run: `py -3.12 -m pytest tests/studio/test_api_key_management.py tests/studio/test_provider_credential_management.py -q`

- [x] **Step 3: Implement routes over existing managers/vault**

Do not place secrets in URL parameters, exception strings, model reprs, audit payloads, or response metadata.

- [x] **Step 4: Run security regressions**

Run: `py -3.12 -m pytest tests/studio/test_api_key_management.py tests/studio/test_provider_credential_management.py tests/auth/test_durable_api_keys.py tests/security/test_durable_secrets.py -q`

### Task 7: Phase 13A disposable integration gate

**Files:**
- Create: `tests/db/test_phase13_live_integration.py`
- Create: `Codex Fix/evidence/phase-13a/VERIFICATION.md`
- Modify: `Codex Fix/EXECUTION_TRACKER.md`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: sanitized evidence for fresh migration, RLS isolation, invitation/revision concurrency, credential redaction, and operational pagination.

- [x] **Step 1: Run the complete forced-offline Python gate**

Run: `py -3.12 -m pytest tests/studio tests/auth tests/agents tests/providers tests/rag tests/post_call tests/telephony -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13a`

- [x] **Step 2: Give Hamzi one disposable PostgreSQL/Redis command**

Use a random local password, `UCVE_ENV=test`, live DB/Redis flags only, live providers off, and `tests/db/test_phase13_live_integration.py`. Expected: all pass and containers/volumes are removed.

- [x] **Step 3: Run static/security checks**

Run changed-file Ruff, compile, migration integrity, `git diff --check`, protected-path scan, and credential-pattern scan. Record counts and limitations without secret values.

- [x] **Step 4: Stop for review and commit confirmation**

Do not begin 13B until Hamzi approves the 13A evidence and explicitly authorizes commit/push.

## Phase 13B — Studio shell and secure BFF

### Task 8: Scaffold the Studio and server-only data boundary

**Files:**
- Create: `studio/package.json`, `studio/package-lock.json`, `studio/tsconfig.json`, `studio/next.config.ts`, `studio/eslint.config.mjs`, `studio/vitest.config.ts`, `studio/playwright.config.ts`
- Create: `studio/src/app/layout.tsx`, `studio/src/app/page.tsx`, `studio/src/app/error.tsx`, `studio/src/app/not-found.tsx`
- Create: `studio/src/data/control-plane.ts`, `studio/src/data/dto.ts`, `studio/src/data/schema.ts`
- Create: `studio/tests/data-boundary.test.ts`

**Interfaces:**
- Produces: `controlPlaneRequest<T>(path, options) -> Promise<T>` in a `server-only` module.
- Produces: safe Zod DTO parsing at the FastAPI boundary.
- Requires: server requests have timeout, request ID, selected tenant, and sanitized error mapping.

- [x] **Step 1: Lock supported dependencies**

Install latest stable Next.js 16.x security patch, React 19 compatible patch, TypeScript, Zod, Vitest, Testing Library, Playwright, and axe-core. Record `npm audit --omit=dev` results; do not accept an unresolved high/critical production vulnerability.

- [x] **Step 2: Write failing DAL boundary tests**

Test missing session, timeout, invalid DTO, upstream 401/403/409/422/429/503 mapping, request-ID preservation, header allowlist, and secret-free errors.

- [x] **Step 3: Implement the minimal shell and DAL**

Use Server Components by default. Client Components receive safe DTOs only. Do not make Server Components call the app's own route handlers.

- [x] **Step 4: Verify**

Run: `npm.cmd --prefix studio run typecheck`, `npm.cmd --prefix studio run lint`, and `npm.cmd --prefix studio run test`.

### Task 9: OIDC session, workspace selection, and role-aware shell

**Files:**
- Create: `studio/src/auth/config.ts`, `studio/src/auth/session.ts`, `studio/src/auth/workspace.ts`
- Create: `studio/src/app/sign-in/page.tsx`, `studio/src/app/workspaces/page.tsx`, `studio/src/app/(studio)/layout.tsx`
- Create: `studio/src/features/workspaces/` components/actions
- Create: `studio/tests/auth-session.test.ts`, `studio/tests/workspace-access.test.tsx`
- Create: `studio/e2e/auth-workspaces.spec.ts`

**Interfaces:**
- Produces: `requireSession() -> StudioSession` and `requireWorkspace(permission?) -> WorkspaceContext`.
- Produces: signed/HTTP-only selected-workspace cookie containing only a workspace identifier.
- Consumes: `GET /v1/me` and organization/invitation APIs.

- [x] **Step 1: Pause if an OIDC provider is not selected**

Hamzi supplies provider choice and confirms required environment variable names are locally configured. Do not request or display values.

- [x] **Step 2: Write failing session/workspace tests**

Test cookie flags, token server-only behavior, invitation handoff, no-membership flow, two tenants, role-based navigation, forged workspace cookie, expired session, and sign-out.

- [x] **Step 3: Implement OIDC and workspace shell**

Use Authorization Code + PKCE via the selected maintained library. Repeat permission checks in DAL/mutations; navigation hiding is not authorization.

- [x] **Step 4: Run unit and offline E2E tests**

Run: `npm.cmd --prefix studio run test` and `npm.cmd --prefix studio run test:e2e -- auth-workspaces.spec.ts`.

- [x] **Step 5: Stop for 13B review and commit confirmation**

Verify client storage contains no tokens and built client chunks contain no server secrets. Do not begin 13C without approval.

## Phase 13C — Guided agent builder

### Task 10: Resumable onboarding, templates, and agent draft editor

**Files:**
- Create: `studio/src/app/(studio)/onboarding/page.tsx`
- Create: `studio/src/app/(studio)/agents/page.tsx`
- Create: `studio/src/app/(studio)/agents/new/page.tsx`
- Create: `studio/src/app/(studio)/agents/[agentId]/build/page.tsx`
- Create: `studio/src/features/onboarding/`
- Create: `studio/src/features/agents/`
- Create: `studio/tests/agent-builder.test.tsx`
- Create: `studio/e2e/agent-builder.spec.ts`

**Interfaces:**
- Consumes: onboarding, template, catalog, agent CRUD, validate, publish, version, and restore APIs.
- Produces: debounced revision-aware draft actions with explicit saved/saving/conflict/error states.

- [x] **Step 1: Write failing component/journey tests**

Cover template and custom paths, resume, validation paths, entitlement limits, stale conflict recovery, publish checklist, immutable version history, restore-to-draft, viewer read-only state, and no raw UUID requirement.

- [x] **Step 2: Implement guided fields and readiness**

Expose safe structured fields. Keep raw prompt/provider configuration in Advanced mode. Never infer a readiness success not returned by the API.

- [x] **Step 3: Verify**

Run unit tests, `agent-builder.spec.ts`, typecheck, lint, and production build.

- [x] **Step 4: Stop for 13C review and commit confirmation**

## Phase 13D — Knowledge and browser voice test

### Task 11: Knowledge lifecycle UI

**Files:**
- Create: `studio/src/app/(studio)/knowledge/page.tsx`
- Create: `studio/src/features/knowledge/`
- Create: `studio/tests/knowledge.test.tsx`
- Create: `studio/e2e/knowledge.spec.ts`

**Interfaces:**
- Consumes: Phase 10 create/list/upload/FAQ/source/retry/delete/preview/activate/bind APIs.
- Produces: bounded uploads, honest source state, citation preview, and published binding result.

- [x] **Step 1: Write failing state tests**

Cover unsupported/oversized file, mixed upload states, retryable/permanent failure, deletion, empty retrieval, citations, activation blocked by unfinished sources, and cross-tenant denial.

- [x] **Step 2: Implement the vertical feature**

Do not copy the engineering console DOM. Reuse the durable API/state contract and customer language.

- [x] **Step 3: Verify**

Run unit tests, `knowledge.spec.ts`, typecheck, lint, and build.

### Task 12: Browser realtime voice test

**Files:**
- Create: `studio/src/app/(studio)/agents/[agentId]/test/page.tsx`
- Create: `studio/src/features/voice-test/`
- Modify only if required: `sdk/typescript/src/`
- Create: `studio/tests/voice-test.test.tsx`
- Create: `studio/e2e/voice-test.spec.ts`

**Interfaces:**
- Consumes: Wavia TypeScript SDK and tenant-bound session-mint endpoint.
- Produces: explicit offline/mock/live badge, mic and connection state, transcript, latency waterfall, interruption, quota, and typed failure UI.

- [x] **Step 1: Write failing protocol/UI tests**

Cover permission denial, unsupported browser, disconnected worker, mock transcript/audio, live-disabled state, barge-in clear, quota rejection, token expiry/replay, and session cleanup.

- [x] **Step 2: Implement using the SDK**

Do not reimplement the realtime protocol. If the SDK lacks an interface, add the smallest tested SDK contract first.

- [x] **Step 3: Verify without provider traffic**

Run SDK build/tests, Studio unit/E2E tests, browser console scan, and media-session cleanup assertions with live providers disabled.

- [x] **Step 4: Stop for 13D review and commit confirmation**

## Phase 13E — Channels, credentials, and developer access

### Task 13: Web integration, API keys, provider credentials, and telephony readiness

**Files:**
- Create: `studio/src/app/(studio)/channels/web/page.tsx`
- Create: `studio/src/app/(studio)/channels/telephony/page.tsx`
- Create: `studio/src/app/(studio)/developers/api-keys/page.tsx`
- Create: `studio/src/app/(studio)/settings/providers/page.tsx`
- Create: `studio/src/features/channels/`, `studio/src/features/api-keys/`, `studio/src/features/providers/`
- Create: `studio/tests/channels-credentials.test.tsx`
- Create: `studio/e2e/channels-credentials.spec.ts`

**Interfaces:**
- Consumes: safe credential/API-key/telephony/catalog APIs.
- Produces: install snippets derived from actual package exports and a one-time API-key reveal requiring explicit acknowledgement.

- [ ] **Step 1: Write failing safety/role tests**

Cover viewer denial, one-time key reveal, clipboard without persistence, revoke confirmation, credential form redaction, advanced routing eligibility, unqualified telephony, and absence of purchase/campaign actions.

- [ ] **Step 2: Implement features**

Generated snippets use safe placeholders, never real keys. Telephony remains a readiness/configuration surface.

- [ ] **Step 3: Verify and secret-scan**

Run unit/E2E/type/lint/build, client-bundle token patterns, browser-storage inspection, URL/log inspection, and repository secret-pattern scan.

- [ ] **Step 4: Stop for 13E review and commit confirmation**

## Phase 13F — Conversations and operations

### Task 14: Conversation history, review, usage, and audit

**Files:**
- Create: `studio/src/app/(studio)/conversations/page.tsx`
- Create: `studio/src/app/(studio)/conversations/[callId]/page.tsx`
- Create: `studio/src/app/(studio)/settings/usage/page.tsx`
- Create: `studio/src/app/(studio)/settings/audit/page.tsx`
- Create: `studio/src/features/conversations/`, `studio/src/features/usage/`, `studio/src/features/audit/`
- Create: `studio/tests/operations.test.tsx`
- Create: `studio/e2e/operations.spec.ts`

**Interfaces:**
- Consumes: conversation/intelligence/review/usage/audit APIs.
- Produces: cursor pagination/filtering, transcript/detail, retention-aware recording state, review state, entitlements, and audit history.

- [ ] **Step 1: Write failing operational-state tests**

Cover empty tenant, pagination, filters, pending intelligence, review required, recording unavailable/deleted/consent-blocked, quota exceeded, degraded provider, and viewer/compliance role differences.

- [ ] **Step 2: Implement truthful operational views**

No invented charts, price estimates, summaries, or success rates. Render only durable source data and explicitly label missing periods.

- [ ] **Step 3: Verify**

Run unit/E2E/type/lint/build and two-tenant data-isolation journeys.

- [ ] **Step 4: Stop for 13F review and commit confirmation**

## Phase 13G — Visual system and production QA

### Task 15: Approved visual design pass

**Files:**
- Create after approval: `Codex Fix/phases/13g-design-brief.md`
- Modify: `studio/src/styles/`, shared components, and affected pages
- Create: fresh screenshot artifacts under `Codex Fix/evidence/phase-13g/`

**Interfaces:**
- Consumes: Hamzi's references and approved design brief.
- Produces: coherent theme/tokens/components without changing validated business behavior.

- [ ] **Step 1: Stop and obtain visual references**

Use the design process to turn references into an approved brief. Do not infer the missing direction.

- [ ] **Step 2: Capture baseline screenshots**

Capture critical desktop and 390 px mobile routes before visual changes.

- [ ] **Step 3: Implement the approved system**

Keep feature logic unchanged. Avoid generic AI gradients, cards-inside-cards, decorative fake metrics, and filler copy.

- [ ] **Step 4: Capture fresh filenames and critique**

After every visual batch, use real Playwright screenshots with new filenames, compare against the brief, fix issues, then repeat.

### Task 16: Final Phase 13 verification and close gate

**Files:**
- Create: `Codex Fix/evidence/phase-13/VERIFICATION.md`
- Modify: `Codex Fix/EXECUTION_TRACKER.md`
- Modify: `Codex Fix/TRACEABILITY.md`

**Interfaces:**
- Consumes: Tasks 1–15.
- Produces: complete offline, database, browser, security, accessibility, and artifact evidence.

- [ ] **Step 1: Run the full forced-offline Python suite**

Run the canonical root pytest command with live providers/database/Redis disabled and a disposable basetemp. Record exact pass/skip/fail counts.

- [ ] **Step 2: Run the full Studio gate**

Run `npm.cmd --prefix studio run test`, `typecheck`, `lint`, `build`, production dependency audit, and the complete Playwright suite.

- [ ] **Step 3: Run disposable PostgreSQL/Redis integration**

Hamzi runs the exact sanitized command supplied at this checkpoint. It must cover migration, RLS, identity, invitations, revisions, conversations, and usage. Remove services/volumes afterward.

- [ ] **Step 4: Run security and artifact scans**

Check client chunks/storage/URLs/logs/screenshots for tokens or credentials; check protected paths; run `git diff --check`, changed-file Ruff/compile, migration integrity, and no-live-network tests.

- [ ] **Step 5: Inspect required browser journeys**

Verify owner/editor/viewer/compliance roles, two tenants, first-user onboarding, invitation, build/publish/restore, knowledge, offline voice test, API-key lifecycle, telephony-not-qualified, conversations, retention/deletion, usage, audit, keyboard navigation, reduced motion, and 390 px overflow.

- [ ] **Step 6: Obtain Hamzi's screenshot approval**

Phase 13 remains `READY FOR FINAL QA` until Hamzi approves the critical desktop/mobile screenshots.

- [ ] **Step 7: Request commit and push confirmation**

Only after all gates pass, ask Hamzi to authorize the clean Phase 13 commit/push. Do not start Phase 14.

## Execution handoff

Execute natively, one subphase at a time, because the contracts are sequential and Hamzi prefers token-efficient phase checkpoints. Start with Phase 13A only. At every subphase:

1. create or confirm a rollback point;
2. implement the listed tasks with TDD;
3. run the listed forced-offline gate;
4. write sanitized evidence;
5. stop for Hamzi's review and separate commit/push confirmation.

**Next exact action:** Review Phase 13D Task 12 evidence, then obtain Hamzi's explicit approval before committing and pushing the Phase 13D branch. Do not begin Phase 13E until that checkpoint is accepted.
