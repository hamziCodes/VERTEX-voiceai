# Wavia Fix Source of Truth and Project Handover

**Checkpoint date:** 2026-11-09 (PKT)

**Canonical development branch:** `wavia-fixv1`

**Current implementation checkpoint:** Phases 13H, 13I and 13J complete locally (2026-11-12); stopped for Hamzi's review before Phase 13K. Nothing pushed. Sections 7 and 18 below describe the earlier Task 6 checkpoint; `Codex Fix/evidence/phase-13h/` and `EXECUTION_TRACKER.md` hold the current state.

**Purpose:** Preserve the decisions, evidence, operating rules, completed work, known limits and exact continuation path for the Wavia production-remediation program.

This document is a handover and decision ledger. It does not replace the detailed audit, executable phase plans or verification evidence. If two documents appear to disagree, use the authority order below and reconcile the stale document before changing code.

## 1. Authority order

1. Security and repository rules in `AGENTS.md`.
2. The current code, migrations, tests and generated contracts on `wavia-fixv1`.
3. `Codex Fix/EXECUTION_TRACKER.md` for phase status and evidence pointers.
4. The active phase plan under `Codex Fix/phases/`.
5. Phase evidence under `Codex Fix/evidence/`.
6. `Codex Fix/HUMAN_INPUT.md` for Hamzi's recorded product and safety decisions.
7. `Codex Fix/IMPLEMENTATION.md`, `TRACEABILITY.md`, `VERIFICATION.md` and this handover for program-level intent.
8. `AUDIT.md` for the original static findings.
9. `legacy_codebases/` and `docs/archive/` as read-only comparison/history, never current runtime truth.

Historical blueprints may describe intent that has since been implemented or superseded. A blueprint statement is not runtime proof. A green offline test is not proof that a paid provider, carrier, deployment or real device works.

## 2. Non-negotiable operating rules

- Never push to `main`. `wavia-fixv1` is the source branch for this remediation program.
- Create a rollback commit before risky multi-file work. Use a phase branch/worktree and merge only verified units into `wavia-fixv1`.
- Never read or expose secret values. Do not read raw API-key files. Environment files may be inspected only for variable names unless Hamzi explicitly grants more access.
- Never commit `.env`, raw keys, tokens, invitation URLs, customer transcripts or credential-shaped fixtures.
- Never change `.github/workflows`, deploy, publish packages, buy numbers, place live calls, contact paid providers or incur charges without explicit approval.
- Test doubles must be labeled. Production must never silently fall back to mock transcripts, replies, tones, recordings, extraction, webhooks or provider success.
- Use failure-first focused tests, then related regression tests, then the phase close gate. Do not call a phase complete because code merely exists.
- Keep screenshots and disposable artifacts under gitignored `hamza_local/`; do not commit them unless Hamzi asks.
- Preserve unrelated user changes and old worktrees. Do not delete or flatten compatibility paths without a separately approved migration.
- Final claims must name what was actually run. Safari, real devices, screen readers, Lighthouse, live providers and live Telnyx are unverified unless evidence says otherwise.

## 3. Product scope and deployment models

Wavia is one multi-tenant voice-agent engine exposed through three delivery models:

| Model | Intended experience | Shared foundation |
|---|---|---|
| Packaged SDK | Developers receive versioned Python/TypeScript packages, obtain Wavia-issued or approved tenant credentials, mint scoped sessions and integrate web voice | Realtime v1 protocol, immutable published plan, API keys, provider policy, usage and integration guidance |
| Done-for-you / enterprise | Wavia or an enterprise implementer configures the customer's agents using advanced controls without forking the engine | Same tenant, agent, knowledge, provider, telephony, privacy and audit contracts |
| Self-serve Studio | Nontechnical owners and staff use guided onboarding to create, configure, test, publish, connect and operate agents | Same FastAPI control plane and runtime contracts, presented through role-aware guided UI |

There are two primary runtime channels:

- **Web voice agent:** browser audio over the sovereign raw WebSocket protocol.
- **Calling agent:** Telnyx-first telephony gateway and media lifecycle. Inbound and controlled single-call outbound exist offline; campaigns, DID purchasing and live certification remain excluded.

One Studio serves all three models. Guided/Advanced is presentation and entitlement, not an authorization boundary. FastAPI and durable membership/capability checks remain authoritative.

## 4. Why latency was bad despite using the same vendors

The legacy applications felt faster because orchestration differed, not because their vendor names were unique. The original Wavia path accumulated latency at several boundaries:

1. Live STT could start only after detected speech, making the first turn pay connection setup and risking early audio.
2. Endpoint fallback waited roughly 960 ms after speech before downstream work could begin.
3. LLM output waited for punctuation or a large word threshold before becoming speakable.
4. The Uplift adapter waited for the complete HTTP body instead of yielding network chunks as they arrived.
5. Connections and components could be cold.
6. Resampling/playout accounting could be lossy or label server enqueue as audible playback.
7. Server cancellation did not prove that queued browser audio was cleared.
8. Worker and UI metrics did not share one truthful turn-correlated event model.

The primary product metric is **acoustic end of user speech to first audible agent sample**, not STT-final-to-server-enqueue. The remediation order was therefore telemetry first, then warm/lossless listening, early LLM-to-TTS streaming, correct DSP/playout, and deterministic interruption. Live vendor comparisons were deliberately postponed until orchestration could be measured honestly.

## 5. Architecture now in place

### Realtime path

```text
Browser or Telnyx media
  -> bounded ingress + canonical audio handling
  -> shared VAD / endpoint decision
  -> warm streaming STT
  -> immutable published agent/session plan
  -> optional bounded knowledge retrieval
  -> streaming LLM
  -> language-aware speakable chunks
  -> streaming TTS + stateful DSP/resampling
  -> bounded egress
  -> client/carrier playback acknowledgement
  -> turn-correlated latency, usage and durable call evidence
```

Interruption cancels generation, stops further server egress, clears scheduled client audio, preserves the user's interrupting words, and commits only agent speech that was actually played.

### Management and durability

- **FastAPI control plane:** identity, authorization, organizations, memberships, agents, immutable versions, catalogs, credentials metadata, knowledge, usage, telephony policy and conversation operations.
- **PostgreSQL/pgvector:** durable tenant data, RLS, agent/runtime configuration, knowledge embeddings, usage, call records, post-call evidence and audit-relevant state.
- **Redis:** replay protection, leases, admission/concurrency and hot coordination where durability semantics require it.
- **Worker jobs:** bounded, leased and idempotent background ingestion, post-call, webhook, deletion and migration work; heavy work stays off the realtime turn.
- **Studio:** Next.js App Router with server-only BFF/DAL. The browser receives safe DTOs and an HTTP-only session, never raw OAuth/provider credentials.
- **Provider layer:** typed contracts, capability catalog, tenant/platform credential binding, health-aware independent STT/LLM/TTS routes and stream-safe failover.
- **Telephony gateway:** verified webhook, durable call lifecycle, bounded media bridge, inbound pipeline, trunk readiness and controlled outbound contract.

PostgreSQL is the durable source of truth. Process memory is not the production queue or tenant authority.

## 6. Completed phase ledger

The exact commands and full counts live in the linked evidence documents and `EXECUTION_TRACKER.md`. The summary below explains what each phase changed and why.

| Phase | Status | What was established | Why it matters |
|---:|---|---|---|
| 00 | Complete | Offline safety harness, separated browser/Telnyx profiles, multilingual fixtures and baseline artifact | Prevented latency work from becoming subjective or mixing web/call profiles |
| Cleanup C00-C06 | Complete | Recoverable ignored quarantine, cache/venv cleanup, duplicate latency layouts removed, package boundaries documented | Reduced clutter without deleting incomplete but contractually meaningful runtime surfaces |
| 01 | Implemented; final human/live QA remains | Canonical turn-correlated latency telemetry across worker, SDK, schemas and demo | Measures the user's real wait and makes stage regressions attributable |
| 02 | Implemented; final endpoint QA remains | Warm STT, shared VAD/Silero integration and lossless bounded ingress | Removes first-turn connection penalty and early-audio loss; endpoint choice remains evidence-driven |
| 03 | Implemented; live provider QA remains | Early speech chunks, true streamed TTS, bounded bridge, timeouts, stateful DSP and configurable playout | Delivers first audio earlier without corrupting continuous audio |
| 04 | Implemented; final listening QA remains | Deterministic barge-in, played-text commits, clear/drain protocol, owned teardown and admission release | Stops ghost speech/tasks and keeps conversation history truthful |
| 05 | Implemented; release QA remains | Realtime v1 protocol and Python/TypeScript SDK 1.0.4 artifacts with generated docs/types | Gives SDK users one versioned public contract; Flutter/LiveKit are roadmap-only |
| 06 | Implemented; release QA remains | Immutable hashed agent plan compiler, signed claims, version pinning and worker verification | Production sessions obey published tenant configuration instead of query-string overrides |
| 07 | Implemented; live vendor qualification remains | Strict provider catalog, typed failures, tenant credential binding, independent routing and stream-safe failover | Supports Wavia-managed and BYOK credentials without fake success or cross-tenant leakage |
| 08 | Implemented; deployment IdP QA remains | Auth context, route policy, API-key lifecycle/RBAC, tenant-bound mint, atomic replay and strict one-use session tokens | Establishes server-side identity and tenancy boundaries |
| 09 | Complete offline/disposable | Migrations/RLS, repositories, Redis leases, durable usage and quotas | Makes configuration, isolation, admission and accounting survive process restarts |
| 10 | Complete offline | Durable knowledge lifecycle, bounded parsing, local embeddings/pgvector, runtime retrieval, real built-in actions, secure disabled-by-default MCP and guided setup | Gives agents grounded business data without blocking the realtime path or enabling unsafe integrations |
| 11 | Complete offline | Durable call records, post-call intelligence/review, webhooks, privacy policy, retention, deletion/erasure, storage and legacy-secret migration | Makes transcripts/recordings/results honest, consent-aware and recoverable |
| 12 | Complete offline; live certification deferred | Verified Telnyx webhook, durable lifecycle, bounded media, inbound pipeline, trunk readiness and controlled outbound | Establishes the calling-agent path without placing a chargeable call |
| 13A | Complete | Studio control-plane contracts and tenant-safe foundation | Supplies real APIs rather than a mock-only dashboard |
| 13B | Complete | WorkOS AuthKit workspace authentication and server-side session boundary | Gives Studio a maintained OIDC implementation without browser-held tokens |
| 13C | Complete | Guided agent builder and immutable draft/publish flows | Enables safe nontechnical configuration on production contracts |
| 13D | Complete | Knowledge lifecycle and browser realtime voice testing | Connects Studio to the already verified knowledge and SDK paths |
| 13E | Complete | Channels, API-key/provider credential metadata and readiness management | Supports SDK/web/telephony setup without exposing secret values |
| 13F | Complete and published to source branch | Conversation and operational views | Exposes durable call/transcript/intelligence states truthfully |
| 13G | Complete locally and verified | Theme B application shell, Agent Directory and Persona Editor visual pilot | Established the professional dashboard direction without redesigning the marketing site or altering behavior |
| 13H Tasks 1-6 | Complete and verified checkpoint | Lean developer role, server capabilities, responsive persistent shell, secure entry/workspace screens, dashboard/onboarding/create-agent screens and global Test selector | Makes the customer foundation permission-aware, composed and usable while keeping session/provider activation explicit |

## 7. Phase 13H exact checkpoint

### Completed commits

| Task | Commit | Outcome |
|---:|---|---|
| Plan | `c98119d` | Approved executable plan for the customer access/shell checkpoint |
| 1 | `83e6b73` | Added `tenant_developer`, explicit backend permission bundle, safe membership capabilities and migration 031 |
| 2 | `176dd8e` | Studio consumes server-returned capabilities; role text no longer acts as a client authorization matrix |
| 3 | `361f54b` | Responsive persistent dashboard shell, compact spacing/type and saved sidebar collapse behavior |
| 4 | `bb8668c` | Composed sign-in, workspace and secure entry surfaces with shared primitives/states |
| 5 | `6965b3d` | Composed dashboard, resumable onboarding and truthful agent creation states |
| 6 | `635fa15` | Added `/test` selector; published agents can open the existing sandbox, drafts explain why unavailable, viewers remain read-only |

### Latest Task 6 verification

- Studio unit/integration tests: **13 files, 119 tests passed** with one worker.
- TypeScript typecheck: passed.
- Lint: passed with zero warnings.
- Production build: passed; `/test` is present in the route output.
- Focused offline Chromium voice journey: **1 passed**.
- The selector itself does not request microphone permission, mint a session or contact any provider. Only the explicit start action inside the existing per-agent sandbox can do that.
- The offline journey verified the deterministic transcript/audio/latency/barge-in/cleanup contract. It did not prove live Gladia, Groq, Cartesia, Uplift or Telnyx behavior.

### Not yet done in Phase 13H

**Task 7 — Workspace Settings and Members management** has not started. It must add `/settings` and `/settings/members`, safe member/invitation data/actions, exact five-role selection, one-time invitation reveal, role updates, removal confirmation, replay/expiry handling and last-admin protection.

**Task 8 — Phase close gate** has not started. It must run focused and full forced-offline Python checks, migration 031 against disposable PostgreSQL, the complete Studio suite/build/e2e set, integrity/security scans, and desktop/mobile visual QA. Only then may Phase 13H be marked complete.

## 8. Authorization decisions

### Launch customer roles — exactly five

| Role | Purpose | Boundary |
|---|---|---|
| `tenant_admin` | Business owner / self-serve administrator | Tenant configuration, members, eligible credentials/keys/channels/agents/usage/audit; protected by last-admin rule |
| `tenant_editor` | Staff member / enterprise implementer | Builds and operates agents within granted tenant capabilities; cannot own member/security administration |
| `tenant_developer` | SDK/integration developer | Reads agent/session/catalog metadata, tests eligible agents, manages eligible API keys and reads provider metadata; cannot manage members, onboarding, stored provider secrets, compliance or telephony policy |
| `tenant_viewer` | Read-only operator | Can inspect permitted tenant state but cannot mutate or start privileged workflows |
| `compliance_admin` | Conversation/review/audit operator | Accesses permitted conversations, reviews, legal/compliance workflows and audit evidence; cannot administer agents or credentials |

No `tenant_owner` exists yet because billing, ownership transfer and workspace deletion are not implemented. Adding an owner label without irreversible owner responsibilities would add management complexity without value.

Human roles and machine/API-key roles are separate. API keys continue to use the supported `tenant_viewer` and `tenant_editor` machine roles/scopes; they are not renamed to `tenant_developer`.

FastAPI produces explicit safe capability strings. Studio uses capabilities for navigation and presentation, while server actions and FastAPI repeat authorization. Unknown roles/capabilities fail closed. Client-side hiding is never a security boundary.

### Platform staff access

The complete operations design proposes a separately protected `/admin` area with durable `platform_admin` and narrowly scoped support access. This is **not implemented in Phase 13H**. The existing boolean/wildcard platform-admin model must eventually be migrated rather than expanded casually.

Separate platform operations/auditor roles, support impersonation, break-glass UI and a separate internal deployment are postponed until actual staffing/compliance needs justify them. This keeps launch roles lean and avoids a role explosion.

## 9. Provider and credential strategy

The provider contract is stage-based: STT, LLM and TTS adapters expose typed capabilities and failures. Selection considers language, model/voice compatibility, credential tier, health and tenant policy. Each stage may fail over independently without replaying already emitted audio or fabricating success.

Approved credential modes:

- `platform`: only Wavia-managed keys.
- `byok`: only tenant-managed encrypted credential references.
- explicit `both`: tenant credential preferred, Wavia credential as allowed fallback.

Approved initial routing policy:

- STT: Gladia → Deepgram for English, Urdu, Arabic and Malay.
- LLM: Groq → Gemini for those languages, with OpenAI optional.
- TTS: Uplift → Cartesia for Urdu; Cartesia → ElevenLabs for English, Arabic and Malay.

These are policy defaults, not permanent hardcoding or proof of live qualification. Guided users receive recommended routing. Advanced eligible users may inspect/change compatible chains. The UI must distinguish configured, verified offline, qualified live, degraded and unavailable.

## 10. Knowledge, actions and the removed “hypercodes” term

“Hypercodes” was removed because no definition, documentation, schema or implementation existed. We did not invent a feature to preserve an undefined label.

Phase 10 instead implemented practical business knowledge:

- Supported: PDF, DOCX, TXT, Markdown, CSV, XLSX and FAQ JSON.
- Bounded extraction, safe signatures/MIME/archive limits, durable status and typed errors.
- Local 384-dimensional embeddings and pgvector search with explicit migration protection.
- Agent/version-scoped retrieval with citations and a bounded realtime deadline.
- Real built-in lifecycle actions and a secure MCP boundary.
- External CRM, calendar, email, inventory, payments and similar systems remain disabled until each has an explicit schema, credential reference, permission, timeout, replay policy, tests and human approval.

Legacy `.doc`, PowerPoint, archives, images, audio/video, OCR, URL crawling and website ingestion are deferred. URL ingestion requires separate SSRF, freshness, robots/legal and fetcher controls.

## 11. Telephony decisions

- Carrier: Telnyx first.
- Direction: inbound first, then controlled one-call outbound.
- Excluded: campaigns, predictive dialing, number purchase/provisioning and hidden live qualification.
- Live gate: H15 must define an approved number/destination allowlist and spend cap before any call.
- Studio may show readiness/configuration, but must not claim a live-ready carrier until live evidence exists.
- Raw WebSocket remains the v1 sovereign SDK path. LiveKit is optional/roadmap-only, not required by Wavia's engine.

## 12. Privacy and post-call decisions

- Recording is off until the tenant explicitly enables it and caller consent is established.
- Default retention: 30 days for transcripts/results and 7 days for consented recordings.
- Protected deployments require a declared storage region; there is no silent cross-region fallback.
- Sensitive, uncertain, high-risk or configured external actions require human review.
- Webhooks are signed, durable, leased and retried through bounded state; success is never simulated.
- Deletion/erasure is restartable and evidence-aware. Audit tombstones may remain where policy requires, without retaining deleted content or secret values.

## 13. Studio design and product decisions

- Studio is the operational dashboard, not the marketing website.
- Wavia Theme B is authoritative for Studio: warm paper/cream surfaces, ink text and marigold as the single brand accent.
- Exact approved core tokens: paper `#FFF6E5`, light surface `#FFFBF2`, warm surfaces `#FBEACD` / `#F6E6C8`, ink `#1C1408`, marigold-dark accent `#B45309`.
- Instrument Sans is the operational UI font. Space Mono is for IDs/logs/latency/technical values. Bricolage Grotesque is limited to the wordmark and major titles. Instrument Serif is not used for controls/data.
- The older VERTEX navy/Inter system and later unrelated website theme are superseded for this surface.
- Persistent collapsible sidebar, contextual top bar, compact density, capped readable content and application radii at or below 24px.
- No marketing hero, gradients, glass cards, decorative blobs, scroll storytelling or generic AI-template presentation.
- Functional status colors are semantic and include text/icon meaning; marigold remains the only brand accent.
- The app currently has no dark-theme mechanism, so Phase 13G did not invent one only to satisfy an old checklist.
- Visual direction was established with a two-screen pilot. Functional route completion and role journeys come before the final decorative consistency pass.
- No image generation or paid multi-model critic was used. Browser screenshots are verification of the actual running app, not generated concepts.

## 14. Cleanup and repository structure decisions

Cleanup was conservative and recoverable:

- Local quarantine: `hamza_local/clean_codebase/` (ignored).
- Removed tracked duplicates: `tests/latency-benchmarks/harness.py` and `tests/latency_benchmarks/__init__.py`; canonical latency tests live in `tests/latency/`.
- Generated caches, `__pycache__` and a stale environment were quarantined locally.
- `legacy_codebases/` remains read-only reference material and is excluded from packages/test discovery.
- Canonical Python packages keep underscore names (`control_plane`, `worker_raw`, `telephony_gateway`, `post_call`). Distribution/service names may remain hyphenated.
- Compatibility paths `control-plane/` and `worker-raw/` remain because tests and layout contracts still consume them.
- Incomplete workers/transports/jobs were not labeled dead merely because they were unfinished; contractual/test/deployment consumers had to be assessed first.

Known older cleanup findings such as lock/dependency metadata, import-time environment behavior and style debt must be judged against current code before opening a new fix. They are historical findings, not automatically current defects.

## 15. Verification model

### Default offline safety flags

Use explicit test/development configuration and keep live gates disabled unless a phase specifically authorizes them:

```powershell
$env:UCVE_ENV='test'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
```

Mock-provider tests must additionally opt into the mock fixture path. A UI “offline mock” badge means VAD/UI/protocol behavior is under test; it does not mean live STT/LLM/TTS is broken.

### Resource-conscious local commands

- Python: use Python 3.12 and the repository's frozen environment where the phase plan specifies it.
- Studio tests: `npm.cmd test -- --maxWorkers=1` on this Windows host.
- Studio build: set `CIRCLE_NODE_TOTAL=1` before `npm.cmd run build` to keep memory bounded.
- Playwright: use isolated ports and the offline auth/control-plane fixture; save screenshots under `hamza_local/`.
- Database/Redis: use the disposable Compose profile with generated local credentials, loopback ports and volume removal after evidence.

The full phase close command set comes from the active phase plan, not from this summary.

## 16. Deferred and unverified work

### Immediate

- Phase 13H Task 7 Settings/Members.
- Phase 13H Task 8 full close gate and evidence.

### Subsequent Studio rollout

- Phase 13I: customer operational surfaces and role journeys using existing production contracts; no dead navigation.
- Phase 13J: lean durable platform-management security foundation, replacing wildcard/boolean platform authorization.
- Phase 13K: internal operations/support-session workflows, complete multi-role QA and final visual consistency pass.

Dedicated language/voice, provider-chain, tools/MCP, extraction, per-agent telephony, compliance, review and live-monitoring routes remain gated until contract audits confirm backend support. Existing consolidated controls stay available instead of creating fake screens.

### Program phases after Studio

- Phase 14: operational readiness, exported telemetry/alerts, job health, capacity, privacy/compliance claims, recovery and final dead-code classification. H14 (hosting target and launch compliance claims) is open.
- Phase 15: packaging, installability, upgrade/release qualification, live carrier/provider certification and approved publishing/deployment. H15 is open.

### Explicitly not proven yet

- Contractual production latency SLOs on real provider/network samples.
- Live Gladia/Deepgram/Groq/Gemini/OpenAI/Uplift/Cartesia/ElevenLabs qualification.
- Live Telnyx call quality, PSTN jitter, carrier provisioning or spend behavior.
- Shared/production database migrations.
- Production deployment, scaling and recovery drills.
- Safari, real mobile devices, manual screen-reader coverage and Lighthouse release targets.
- Package publication to public registries.
- Dark mode, because no product theme mechanism currently exists.

## 17. Decision dependency map

| Decision | Enables | Constrains / postpones |
|---|---|---|
| Acoustic EOS → audible sample is primary | Honest latency optimization and regressions | Live SLO promises until approved samples exist |
| Published plan is authoritative | Reproducible sessions and tenant safety | Arbitrary production query overrides |
| Raw WebSocket Python/TS are v1 | Focused SDK qualification | Flutter and required LiveKit support |
| FastAPI authoritative + server BFF | One security/domain truth | Client-only role logic and duplicated business rules |
| Five launch customer roles | Manageable least-privilege Studio | Owner/billing and narrow role explosion |
| Capability strings from backend | UI flexibility with fail-closed security | Role-name inference as authorization |
| Platform/BYOK/both credential modes | Self-serve and enterprise delivery | Secret values in Studio or cross-tier silent fallback |
| Local embeddings + bounded retrieval | Predictable knowledge cost/latency | Automatic external embedding dependency |
| Telnyx-first controlled telephony | One carrier path to certify | Campaigns, purchases and unapproved calls |
| Privacy-first recording defaults | Safer launch and truthful evidence | Recording without enablement/consent |
| Theme B operational dashboard | Consistent Studio rollout | Old VERTEX palette and marketing-page composition |
| Offline-first verification | Safe, repeatable development | Claims about live provider/carrier quality |

## 18. Exact continuation game plan

### Next action: Phase 13H Task 7

1. Confirm `wavia-fixv1` is clean and create/continue an isolated Phase 13H worktree branch from the integrated checkpoint.
2. Read the Task 7 section and existing organization member/invitation endpoints before editing.
3. Write failing tests for:
   - read-only member list;
   - admin invitation with exactly the five roles;
   - explicit warning when granting `tenant_admin`;
   - one-time invitation URL reveal with no browser persistence/logging;
   - role update and removal confirmation;
   - last-admin conflict;
   - expired/replayed invitation messages;
   - no token in rendered member/invitation lists.
4. Implement `/settings`, `/settings/members`, safe typed data/action boundaries and the composed management UI.
5. Require `member:read` for the route; require `member:write` for mutation controls and recheck authorization server-side.
6. Run focused Vitest and the offline Playwright member journey.
7. Inspect the diff for secret/token leakage, forged capability behavior, cross-tenant access and protected paths.
8. Commit only Task 7 as `feat(studio): add workspace member management`.

### Then: Phase 13H Task 8

1. Run all focused Phase 13H Python authorization/migration tests and the full forced-offline Python suite.
2. Run Ruff, scoped mypy and compile checks for changed Python modules.
3. Apply migrations through 031 in disposable PostgreSQL, verify constraints/RLS/idempotency and remove containers/volumes.
4. Run all Studio tests, typecheck, lint, production build and full offline Chromium suite.
5. Run plan integrity, `git diff --check`, protected-path, secret-signature, client-bundle token, hardcoded-color/gradient and role/capability parity scans.
6. Capture and inspect actual desktop and 390px views for workspace selection, dashboard, onboarding, creation, test selector and members. Check keyboard focus, overflow, mobile drawer, saved collapse state and console.
7. Write `Codex Fix/evidence/phase-13h/PROGRESS.md` and `VERIFICATION.md`, update the tracker and project profile with exact evidence and limits.
8. Commit `test(studio): close phase 13h customer foundation`, stop and request Hamzi's review. Do not begin Phase 13I automatically.

### Copy-ready continuation prompt

> Continue Wavia from `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md`. Verify the active branch is based on the latest `wavia-fixv1`, keep live providers/calls/deployments disabled, and execute only Phase 13H Task 7 from `Codex Fix/phases/13h-customer-access-shell-completion-implementation-plan.md` with failure-first tests. Do not start Task 8 until Task 7 is committed and its focused Vitest/Playwright verification passes. Never read secret values or touch `.github/workflows`.

## 19. Human intervention still required

No human action is required to begin the offline Task 7 implementation.

Hamzi will be needed later for:

- reviewing the completed Phase 13H customer foundation after Task 8;
- supplying/approving production WorkOS domains, redirects and credentials without sharing values in chat;
- H14 hosting target and launch compliance claims;
- H15 live provider/carrier destination, number, budget and spend approvals;
- any shared database migration, deployment, package publication or workflow change;
- final real-user/device/accessibility and live quality acceptance.

## 20. Checkpoint integrity statement

At this checkpoint, no live call, paid provider request, deployment, package publication or external critic/image-generation spend was used. No secret value belongs in this report. Phase 13H is deliberately **not** marked complete: Tasks 1-6 are implemented; Tasks 7-8 remain the next controlled work.
