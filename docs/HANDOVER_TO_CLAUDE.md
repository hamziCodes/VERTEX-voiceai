# Wavia Engine Handover to Claude

**Definitive handover date:** 2026-11-10 (PKT)

**Repository:** `https://github.com/hamziCodes/VERTEX-voiceai`

**Required branch:** `wavia-fixv1` — never `main`

**Recorded HEAD at handover:** `fad38e85892a15eff3d348a0d5a7a5d33f230de4` (`docs(wavia): record remediation source of truth`)

**Scope of this document:** Recorded project state plus a light repository check only. It is not a new audit, fresh runtime proof, or a replacement for the phase evidence.

## 1. What Wavia is

Wavia is a multi-tenant, real-time voice-agent platform built around the Unified Core Voice Engine (UCVE). It serves three delivery models from one set of contracts:

- packaged Python and TypeScript SDKs for developers;
- done-for-you/enterprise agent builds with advanced configuration; and
- self-serve Wavia Studio for nontechnical customers.

It has two intended conversation channels: browser audio over a raw WebSocket realtime protocol, and Telnyx-first phone calling through the telephony gateway. The goal is a tenant-safe, observable engine that gets from the end of a caller's speech to first audible agent audio quickly and honestly.

## 2. What exists today

The following is recorded implementation, not a claim of live production certification.

| Surface | Current recorded state |
|---|---|
| Core realtime engine | Canonical audio/frame contracts, VAD/endpointing, warm streaming STT, streaming LLM-to-TTS, bounded queues, stateful DSP/resampling, playout acknowledgement, cancellation and barge-in lifecycle work are implemented through the remediation phases. |
| Worker and protocol | `worker_raw/` runs the raw WebSocket path; Realtime v1 contracts and Python/TypeScript SDK 1.0.4 artifacts are recorded as implemented. Flutter and required LiveKit support are explicitly roadmap-only. |
| Control plane | FastAPI control plane has durable tenant identity/RBAC, agent drafts/published immutable versions, provider catalog/credentials metadata, knowledge, usage/quotas, organizations/memberships, invitations and conversation operations contracts. |
| Persistence | PostgreSQL/pgvector migrations, RLS repositories, Redis leases/replay/admission, durable usage, knowledge, call/post-call state, retention and erasure were verified offline/disposably in their owning phases. |
| Knowledge/actions | Bounded PDF, DOCX, TXT, Markdown, CSV, XLSX and FAQ ingestion; local embeddings/pgvector retrieval; citations; bounded runtime lookup; real lifecycle actions; and a disabled-by-default MCP boundary exist. External business systems are not automatically enabled. |
| Providers | Typed STT/LLM/TTS adapter contracts, tenant/platform/BYOK credential selection, independent stage routing, health/failover and typed failures are implemented. Live qualification is not recorded. |
| Telephony | Telnyx webhook security, durable lifecycle, bounded media bridge, inbound pipeline, trunk readiness and controlled single-call outbound were implemented/tested offline. No live carrier certification, campaign support, DID purchase or unapproved calling is recorded. |
| Privacy/post-call | Consent-aware recording, transcripts/results, review/extraction, signed webhooks, redaction, retention, object storage boundary, deletion/erasure and audit-aware migration behavior are implemented offline. |
| Studio | Next.js Studio with WorkOS AuthKit, server-side BFF/DAL, workspace selection, guided onboarding, agent creation/build/publish, knowledge, browser voice test, channel/credential/usage/audit/conversation views, and an approved visual shell/pilot exists. |
| Studio checkpoint | Phase 13H Tasks 1–6 are recorded complete: lean developer role, server-returned capabilities, responsive collapsible shell, entry/workspace surfaces, dashboard/onboarding/create-agent screens, and global agent Test selector. Settings/Members and Phase 13H close gate remain. |

The Studio must use FastAPI as the authorization and domain authority. The browser receives safe DTOs and a secure session boundary; it must never be trusted with tenant identity, provider credentials, OAuth refresh tokens or arbitrary production overrides.

## 3. Recorded phase status

Phase 00 is the baseline/safety harness. The delivery roadmap is Phases 01–15. The tracker has a row for 00–15, so it contains sixteen numbered rows in total.

| Phase | Recorded status | Delivered / remaining |
|---:|---|---|
| 00 | Done | Offline latency/safety harness, separated browser/Telnyx profiles, multilingual fixtures and baseline artifact. |
| 01 | In progress — implementation verified, human/final QA pending | Truthful turn-correlated latency telemetry. Needs local three-turn browser check and eventual approved live evidence. |
| 02 | In progress — implementation verified, final QA pending | Silero/shared VAD, warm/lossless streaming STT ingress. Endpoint trade-off H04 remains evidence-gated. |
| 03 | In progress — implementation verified, final QA pending | Early LLM-to-TTS chunks, true TTS streaming, bounded bridge, timeout/DSP/playout work. Needs provider/multilingual/jitter QA. |
| 04 | In progress — implementation verified, final QA pending | Deterministic interruption, browser clear/drain and owned teardown. Needs listening acceptance/browser QA. |
| 05 | In progress — implementation verified, final QA pending | Realtime v1 protocol and Python/TypeScript SDK parity. Public API/long-running listening review remains. |
| 06 | In progress — implementation verified, final QA pending | Immutable agent session compiler, signed claims and published-config authority. Cross-phase final QA remains. |
| 07 | In progress — implementation verified, final QA pending | Provider catalog/contracts, tenant credential binding, routing and stream-safe failover. Live provider qualification remains. |
| 08 | In progress — implementation verified, final QA pending | Auth context, route policy, API key lifecycle/RBAC, mint/token hardening. External IdP/deployed Redis validation remains. |
| 09 | Done | Migrations/RLS, repositories, Redis leases, durable usage and quotas; offline and disposable DB/Redis evidence recorded. |
| 10 | Done (offline scope) | Knowledge, supported file ingestion, local vectors/retrieval, actions, secure MCP boundary and guided setup. Requires reviewed local model bundle before production. |
| 11 | Done (offline scope) | Durable call/post-call records, review/webhooks, privacy/redaction, retention/storage/deletion/erasure. |
| 12 | Done (offline scope) | Telnyx-first offline telephony lifecycle and controlled outbound contract. Live carrier certification deferred to Phase 15. |
| 13 | In progress | Studio foundations through 13H Tasks 1–6. Task 7 Settings/Members and Task 8 close gate are not started. Later 13I–13K operational/platform rollout remains. |
| 14 | Not started | Operations/compliance: readiness, telemetry export/alerts, jobs, capacity, recovery, hosting/compliance truth, final dead-code classification. H14 is open. |
| 15 | Not started | Packaging/release qualification, installation/upgrades, approved live provider/carrier certification, deployment/publishing. H15 is open. |

### Does this equal “13 of 15 done”?

No, not under the tracker's strict completion labels. It records five `COMPLETE` rows when Phase 00 is included (`00`, `09`, `10`, `11`, `12`); Phases `01`–`08` have implemented work but still carry final/human QA gates, Phase `13` is incomplete, and Phases `14`–`15` have not started. A looser statement that “most of the engine implementation through Phase 13 exists” is supported, but it must not be presented as 13 fully closed delivery phases.

## 4. Decisions, gates and why they exist

| Decision / date | Why and rejected alternative | Effect on current/future work |
|---|---|---|
| Offline-first, no paid/live traffic unless explicitly approved | Repeatable tests and no accidental cost or customer impact. Rejected: using live providers/carriers as normal development fixtures. | Keep `RUN_LIVE_PROVIDERS=0` and `RUN_LIVE_TELEPHONY=0` by default. H15 controls real calls, destinations and spend. |
| 2026-10-16: acoustic end-of-speech → first audible sample is the primary latency metric | Server enqueue/first token metrics do not equal caller-perceived latency. | Latency changes must preserve turn correlation, word retention, audio continuity and interruption behavior. Live SLOs remain provisional. |
| H04 deferred: endpoint policy waits for evidence | Aggressive endpointing can cut off speakers; balanced/adaptive choices need English, Urdu, mixed speech, pauses and noise evidence. | Do not silently change endpoint defaults as a cosmetic latency fix. |
| 2026-10-20: raw WebSocket Python/TypeScript SDKs are v1; Flutter/LiveKit are roadmap-only | Keeps the public contract focused and avoids pretending incomplete clients are launch-ready. | Do not expand Flutter/required LiveKit work without a new scope decision. |
| 2026-10-20: published agent configuration is authoritative in production | Reproducible, secure sessions; query overrides create drift. | Overrides require an explicit local-development unsafe flag; runtime pins an immutable published plan/version. |
| 2026-10-22: provider strategy is platform, BYOK, or explicit both | Supports self-serve and enterprise without exposing secrets or mixing tenants. Rejected: one implicit credential behavior. | `platform` uses Wavia keys, `byok` tenant keys, `both` prefers tenant keys with permitted platform fallback. Live readiness must be explicit. |
| 2026-10-22: initial provider routes | STT Gladia → Deepgram for en/ur/ar/ms; LLM Groq → Gemini with OpenAI optional; TTS Uplift → Cartesia for Urdu and Cartesia → ElevenLabs for en/ar/ms. | These are policy defaults, not proof of live qualification or permanent hardcoding. |
| 2026-10-22: external OIDC for Studio plus scoped tenant API keys | Uses maintained identity boundary instead of first-party password/OAuth cryptography. | WorkOS/AuthKit and OIDC metadata are required for real Studio sign-in; browser never stores raw access/refresh secrets. |
| 2026-10-23: hypercodes removed | No definition, code, schema or user-facing behavior existed. Rejected: inventing a product feature around an undefined label. | Do not reintroduce it unless there is a new product specification. |
| 2026-10-23: Phase 10 practical knowledge/action scope | Common business files plus FAQ solve real setup needs; external integrations need safer contracts. | Support PDF/DOCX/TXT/Markdown/CSV/XLSX/FAQ. Defer OCR, URLs/crawling, archives, media, PowerPoint and `.doc` until separately designed. |
| 2026-10-26: privacy-first records | Consent and residency matter before recording intelligence. | Recording off until tenant enablement and caller consent; 30-day transcript/result and 7-day consented-recording defaults; human review for sensitive/high-risk actions. |
| 2026-10-26: Telnyx first, inbound first, controlled single-call outbound | Limits carrier risk/cost while a real media path is proven. Rejected: campaigns, predictive dialling, auto provisioning and live testing without approval. | H15 must approve number, destination allowlist and spend cap. |
| 2026-10-29: one standalone Next.js Studio with thin server BFF/DAL | Keeps FastAPI as one business/authorization truth while giving customers an operational UI. | Guided and Advanced presentations are entitlement/role-aware, not security boundaries. No billing/checkout, DID purchase or deployment UI yet. |
| Studio customer roles: exactly five at launch | Least privilege without an unmanageable role explosion. | `tenant_admin`, `tenant_editor`, `tenant_developer`, `tenant_viewer`, `compliance_admin`; no owner/billing role yet. API-key machine roles remain separate. |
| Server returns capabilities; Studio consumes capabilities | Rejected: client-side role name matrix as authorization. | Unknown roles/capabilities fail closed; server actions and FastAPI repeat authorization. |
| Phase 13G visual pilot used the earlier Theme B | It was the accepted Studio direction at that time and established shell/component behavior. | The new Ripple files in Section 9 now govern future dashboard frontend work. This handover does not reconcile or implement their visual migration. |
| Branch/workflow discipline | Protects rollback/review and avoids accidental production changes. | Work only on `wavia-fixv1`; never push to `main`, force-push, modify `.github/workflows`, deploy or publish without explicit approval. |

## 5. Postponed work and dependencies

| Delayed work | Why it is delayed | What it waits on |
|---|---|---|
| Phase 13H Task 7 Settings/Members | It is the next controlled Studio task, not yet implemented. | Existing organization member/invitation contracts; focused tests before implementation. |
| Phase 13H Task 8 close gate | Must validate the complete foundational customer surface after Task 7. | Task 7, full forced-offline Python/Studio tests, disposable PostgreSQL migration 031 proof and browser QA. |
| Phase 13I–13K | Operations/platform routes cannot be honestly added ahead of production contracts. | 13H close, contract audit, durable platform-role model and later functional acceptance. |
| Live latency/provider tests | Could spend money and conflate orchestration defects with provider/network performance. | H15 approval and recorded spend/destination limits. |
| Live Telnyx certification | Calls can create cost and require an approved destination. | H15 number/destination/spend approval. |
| Shared/production DB migration | It is irreversible compared with disposable databases. | Explicit Hamzi approval after migration proof. |
| Production deployment/publishing | Requires a hosting/compliance truth and release evidence. | H14 hosting/compliance decision and H15 release/live approval. |
| Billing/checkout, DID purchase, campaigns | Product/financial and compliance scope is not designed. | Separate approved product specification. |
| OCR, crawling/URL ingestion, external CRM/calendar/email/inventory/payments | Need SSRF/legal/freshness or explicit schema/credentials/permissions/replay controls. | A separate design and tests for each integration. |
| Dark mode, Safari/real device/screen-reader/Lighthouse claims | Not implemented/verified in the recorded evidence. | A later explicit visual/accessibility/release QA pass. |

## 6. Clean stop point and last known verification

The clean stop point is **Phase 13H Task 6**: the truthful global Test selector was added. Published agents can open the existing per-agent browser sandbox; draft-only agents stay visible with an honest disabled reason; viewers can inspect readiness but cannot start the privileged test path. Merely opening the selector does not mint a voice session or contact a provider.

Last recorded implementation commit before this handover documentation: `635fa15 feat(studio): add truthful test entry`. The branch's recorded HEAD before this document is `fad38e8 docs(wavia): record remediation source of truth`.

Last recorded verification at that checkpoint:

- Phase 13H focused Python authorization/migration tests: 39 passed after integration.
- Studio: 13 test files, 119 tests passed (one worker).
- Studio typecheck and zero-warning lint passed.
- Studio production build passed and included `/test`.
- Focused offline Chromium voice journey: 1 passed.
- Plan integrity: 36 phases/tests/trackers verified.

This documentation task did **not** rerun these checks. They are historical recorded evidence; live providers, live telephony, Safari, real devices, screen-reader and production deployment remain unverified.

## 7. Exact resume point and remaining order

### Start here: Phase 13H Task 7 — Workspace Settings and Members

Read `Codex Fix/phases/13h-customer-access-shell-completion-implementation-plan.md` before editing. The first work item is a failing `member-management` test suite covering a read-only editor list, exact five-role invitation choices, a tenant-admin warning, one-time invitation reveal, role updates, removal confirmation, last-admin protection, expired/replayed invitations and no invitation token in rendered lists.

“Done” for Task 7 means the routes `/settings` and `/settings/members`, typed server-only data/actions, capability-gated UI and offline Playwright member journey exist; `member:read` protects the view, `member:write` gates mutations and server-side authorization is repeated. Commit only this task as `feat(studio): add workspace member management`.

Then complete Task 8: full Phase 13H Python/Studio/offline browser/disposable PostgreSQL/safety/visual close gate, evidence files and tracker update. Stop for review after the Task 8 commit; do not silently begin 13I.

The remaining ordered program is: finish 13H → 13I customer operational routes → 13J platform-management security foundation → 13K multi-role operations/support/final Studio QA → Phase 14 operations/compliance → Phase 15 packaging and approved release/live certification. The end state is a fully evidenced, installable, tenant-safe, low-latency web and calling platform—not merely an offline demo—with release evidence for each delivery model.

## 8. Required reading order

1. `docs/HANDOVER_TO_CLAUDE.md` — this exact checkpoint and working agreement.
2. `Codex Fix/WAVIA_FIX_SOURCE_OF_TRUTH.md` — fuller decision ledger, dependency map and detailed Phase 13H continuation.
3. `Codex Fix/EXECUTION_TRACKER.md` — authoritative status/evidence index; do not infer phase completion from commits alone.
4. `Codex Fix/HUMAN_INPUT.md` — recorded approvals and open H14/H15 gates.
5. `Codex Fix/IMPLEMENTATION.md` and `Codex Fix/TRACEABILITY.md` — architecture, phase dependencies and original finding ownership.
6. `Codex Fix/phases/13h-customer-access-shell-completion-implementation-plan.md` — exact next task and close-gate commands.
7. `Codex Fix/evidence/phase-13g/VERIFICATION.md` and relevant Phase 13 evidence — known Studio verification boundaries.
8. `docs/superpowers/specs/2026-11-07-wavia-studio-complete-operations-design.md` — customer/platform operational design and deferred route boundaries.
9. `docs/DESIGN.md` — the saved Ripple design specification; governing reference for future dashboard frontend work.
10. `docs/design/design-tokens.json` — the saved Ripple design tokens; governing reference for future dashboard frontend work.
11. `README.md`, `docs/deploy/COMPOSE_QUICKSTART.md`, `.env.example`, `infra/docker/.env.example` and `docs/developer/env/.env.example` — current setup surfaces.

`docs/DESIGN.md` and `docs/design/design-tokens.json` were copied unchanged from Hamzi's supplied files. Their SHA-256 matches the originals at handover. Together they govern future dashboard frontend work: read and understand both before changing the dashboard, then improve/build against them. Their relationship to the earlier Theme B Studio pilot is intentionally **unreconciled** in this documentation-only pass.

## 9. Standing context Claude must save in persistent project memory

- Repository/branch: `hamziCodes/VERTEX-voiceai`, work on `wavia-fixv1`, never `main`.
- Do not read or expose secret values or raw key files; only inspect environment variable names unless Hamzi grants more.
- No force-push, deployment, publishing, workflow changes, live calls, paid provider traffic, number purchases or spending without explicit approval.
- Create a rollback commit before risky multi-file work. Keep commits small, atomic and phase/task-scoped. Push clean verified phase checkpoints.
- Preserve dirty worktrees/unrelated changes. Do not delete compatibility paths or “dead” code without a separately approved, evidence-based removal.
- FastAPI/control plane is authorization/domain truth. Studio is a server-side BFF/DAL and presentation layer; browser role checks never grant access.
- Production sessions use immutable published plans; test doubles are explicit and must never produce fake production success.
- Latency is judged by acoustic EOS → first audible sample. Never optimize one stage while breaking word retention, audio continuity, interruption or tenant safety.
- Always record exact verification commands/results and label unverified surfaces honestly.
- Phase 13H Task 7 is next; Phase 13H is not complete. The design references at `docs/DESIGN.md` and `docs/design/design-tokens.json` govern future dashboard work, but no visual migration is authorized by this handover alone.

## 10. Fresh-machine setup

These instructions are a setup guide, not proof that they were run during this documentation task.

1. Install Git, Docker Desktop/Compose v2, Python 3.12, `uv`, Node.js **22.11 or later**, and a supported Chromium browser for Playwright.
2. Clone and select the only allowed branch:

   ```powershell
   git clone https://github.com/hamziCodes/VERTEX-voiceai.git
   Set-Location VERTEX-voiceai
   git switch wavia-fixv1
   git status --short --branch
   ```

3. Create local environment files from templates. Leave live-provider and telephony gates disabled until Hamzi explicitly approves them:

   ```powershell
   Copy-Item .env.example .env
   Copy-Item infra/docker/.env.example infra/docker/.env
   ```

4. Fill only the manual values in Section 11. Never commit either `.env` file.
5. Install Python dependencies with the repository's Python 3.12 environment:

   ```powershell
   uv sync --python 3.12
   ```

6. Install the Studio dependencies:

   ```powershell
   Set-Location studio
   npm ci
   Set-Location ..
   ```

7. Start the local Compose stack using its copied local environment file:

   ```powershell
   docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env up -d --build
   ```

   Verify `http://localhost:8080/health` and `http://localhost:8081/health`. Do not add the telephony profile or enable LiveKit unless the relevant task explicitly requires it.

8. Run safe baseline checks before resuming implementation:

   ```powershell
   $env:UCVE_ENV='test'
   $env:RUN_LIVE_PROVIDERS='0'
   $env:RUN_LIVE_TELEPHONY='0'
   uv run --frozen --python 3.12 python voice_engine_plan/scripts/verify_plan_integrity.py
   uv run --frozen --python 3.12 python -m pytest -q
   npm.cmd --prefix studio test -- --maxWorkers=1
   npm.cmd --prefix studio run typecheck
   npm.cmd --prefix studio run lint
   $env:CIRCLE_NODE_TOTAL='1'
   npm.cmd --prefix studio run build
   ```

9. For the next task, do not start the entire app as proof of live voice. Follow the focused Task 7 test commands first. Run Playwright only against its offline fixture unless a live gate is explicitly approved.

## 11. Environment variables

All values are intentionally blank in this handover. “Secret” includes credentials, bearer material, database URLs containing credentials and sensitive observability endpoints. “Configuration” is not inherently secret, but it still must be deployment-specific.

| Variables | Purpose / where used | Secret? |
|---|---|---|
| `UCVE_ENV`, `UCVE_RUNTIME_PROFILE` | Runtime mode/profile; runtime environment loading, Compose and worker/control-plane configuration. | No |
| `RUN_LIVE_PROVIDERS`, `RUN_LIVE_TELEPHONY` | Explicit paid/live provider and carrier safety gates; tests/runtime. | No — safety controls |
| `UCVE_JWT_SECRET`, `UCVE_MINT_HMAC_SECRET`, `UCVE_METRICS_BEARER`, `UCVE_MASTER_KEY` | Session JWT/mint signing, metrics protection and local development envelope encryption; control plane/worker/Compose. | Yes |
| `UCVE_WS_PUBLIC_URL`, `UCVE_TELEPHONY_MEDIA_PUBLIC_URL`, `UCVE_CONTROL_PLANE_URL`, `UCVE_WORKER_WS_URL`, `WAVIA_CONTROL_PLANE_URL`, `UCVE_API_VERSION` | Public/local service URLs and API version; mint responses, SDK host-backend setup, telephony and Studio. | No — configuration |
| `UCVE_ALLOWED_ORIGINS` | CORS allowlist; API/runtime environment. | No — security configuration |
| `DATABASE_URL`, `REDIS_URL` | Database and Redis clients, migrations, Compose/tests. | Yes if credentials are embedded |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` | Local/deployed PostgreSQL connection composition; developer/Compose environment. | No — configuration |
| `POSTGRES_PASSWORD` | PostgreSQL authentication; Compose/developer environment. | Yes |
| `PLATFORM_GROQ_API_KEY`, `GOOGLE_API_KEY`, `PLATFORM_OPENAI_API_KEY`, `PLATFORM_ANTHROPIC_API_KEY` | Server-side LLM adapters and provider credential tests. | Yes |
| `PLATFORM_GLADIA_API_KEY`, `PLATFORM_DEEPGRAM_API_KEY`, `PLATFORM_SONIOX_API_KEY` | Server-side STT adapters and provider routing. | Yes |
| `PLATFORM_UPLIFT_API_KEY`, `PLATFORM_ELEVENLABS_API_KEY`, `PLATFORM_CARTESIA_API_KEY`, `PLATFORM_RIME_API_KEY`, `PLATFORM_FISH_AUDIO_API_KEY`, `CARTESIA_API_KEY` | Server-side TTS adapters and provider routing. | Yes |
| `UPLIFT_VOICE_ID`, `PLATFORM_UPLIFT_VOICE_ID`, `UPLIFT_OUTPUT_FORMAT`, `ELEVENLABS_VOICE_ID`, `PLATFORM_ELEVENLABS_VOICE_ID`, `ELEVENLABS_OUTPUT_FORMAT`, `ELEVENLABS_MODEL_ID`, `CARTESIA_VOICE_ID`, `PLATFORM_CARTESIA_VOICE_ID`, `CARTESIA_MODEL_ID`, `CARTESIA_SAMPLE_RATE`, `CARTESIA_VERSION` | Provider-specific voice/model/output configuration in TTS adapters. | No — configuration |
| `TELNYX_API_KEY`, `TWILIO_AUTH_TOKEN`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Carrier/SFU credentials; telephony gateway or optional LiveKit adapter. | Yes |
| `TELNYX_CONNECTION_ID`, `TELNYX_PUBLIC_KEY`, `TWILIO_ACCOUNT_SID`, `LIVEKIT_URL`, `UCVE_ENABLE_LIVEKIT` | Carrier/SFU identifiers, public verification material, URL and explicit optional transport switch. | No — configuration (treat account/connection IDs as sensitive operational metadata) |
| `AWS_KMS_KEY_ID`, `AWS_REGION`, `GCP_KMS_KEY_NAME` | Production KMS key selection/region; envelope-encryption adapters and Compose. | No — configuration |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `GOOGLE_APPLICATION_CREDENTIALS` | Cloud identity used by KMS/object storage integrations. | Yes |
| `OTEL_EXPORTER_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN` | Telemetry/exporter and error reporting configuration; runtime/Compose. | `SENTRY_DSN` and endpoint should be handled as sensitive; flag is not secret |
| `UCVE_VAD_THRESHOLD`, `UCVE_VAD_MIN_SPEECH_MS`, `UCVE_VAD_MIN_SILENCE_MS`, `UCVE_VAD_PRE_SPEECH_MS`, `UCVE_NOISE_GATE_K`, `UCVE_NOISE_GATE_WINDOW`, `UCVE_NOISE_GATE_DEFAULT_FLOOR` | VAD/noise-gate tuning; worker audio pipeline. | No |
| `UCVE_BARGE_VERIFY_WINDOW_MS`, `UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS`, `UCVE_BARGE_TEXT_BACKUP_WORDS` | Barge-in verification and transcript continuity; worker turn manager. | No |
| `UCVE_GLADIA_ENDPOINTING`, `UCVE_GLADIA_RECEIVE_PARTIALS`, `UCVE_STT_MOCK_TEXT`, `UCVE_STT_CONNECT_TIMEOUT_MS`, `UCVE_STT_RECONNECT_MAX_ATTEMPTS`, `UCVE_INGRESS_BACKPRESSURE_WARN_MS` | STT behavior, mock-only fixture text, timeouts and ingress observability; provider/worker pipeline. | No (mock text must never contain customer data) |
| `UCVE_TTS_CHUNK_SIZE_BYTES`, `UCVE_EGRESS_PREBUFFER_MS`, `UCVE_TTS_FIRST_CHUNK_TIMEOUT_MS`, `UCVE_TTS_INTER_CHUNK_TIMEOUT_MS`, `UCVE_TTS_OVERALL_TIMEOUT_MS` | TTS streaming/backpressure/timeout tuning; worker pipeline. | No |
| `UCVE_CHUNKER_FIRST_WORDS`, `UCVE_CHUNKER_MIN_WORDS`, `UCVE_TOOL_FILLER_DELAY_MS` | LLM speakable-text chunker and tool filler timing; worker pipeline. | No |
| `UCVE_DEBUG_LISTENING`, `UCVE_DEBUG_LATENCY`, `UCVE_DEBUG_ERRORS`, `UCVE_INITIAL_GREETING` | Development diagnostics and optional greeting; worker/control-plane/SDK setup. | No (debug must remain disabled in production) |
| `WORKOS_CLIENT_ID`, `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | WorkOS AuthKit application ID and Studio callback URL; Studio server/client configuration. | No — configuration |
| `WORKOS_COOKIE_PASSWORD` | Studio session-cookie encryption; Studio server. | Yes |
| `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE` | FastAPI OIDC token verification metadata; control-plane identity boundary. | No — configuration |
| `WAVIA_VOICE_TEST_MODE` | Explicit Studio voice-test mode (`offline`, mock or approved live); Studio server. | No — safety configuration |
| `UCVE_TENANT_API_KEY` | Server-side host-backend API key for scoped mint proxy. | Yes |
| `UCVE_PUBLISHABLE_KEY` | Public SDK/client identifier where supported. | No — configuration |

### HAMZI FILLS THESE IN MANUALLY

Copy/provide only the values that apply to the machine and the explicitly approved mode. Do **not** paste them into chat, source, tests or commits.

- Required local security generation: `UCVE_JWT_SECRET`, `UCVE_MINT_HMAC_SECRET`, `UCVE_METRICS_BEARER`, `WORKOS_COOKIE_PASSWORD`; `UCVE_MASTER_KEY` only for local-development encryption where that adapter is used.
- Local database/redis: `POSTGRES_PASSWORD`, `DATABASE_URL`, `REDIS_URL` if not using a fully local unauthenticated disposable test setup.
- Studio authentication: `WORKOS_CLIENT_ID`, `NEXT_PUBLIC_WORKOS_REDIRECT_URI`, `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE`.
- Approved provider credentials only: every applicable `PLATFORM_*_API_KEY`, `GOOGLE_API_KEY`, `CARTESIA_API_KEY`; plus chosen provider voice/model/output identifiers.
- Approved live telephony only: `TELNYX_API_KEY`, `TELNYX_CONNECTION_ID`, `TELNYX_PUBLIC_KEY`, `UCVE_TELEPHONY_MEDIA_PUBLIC_URL`; Twilio/LiveKit values only if those optional paths are separately approved.
- Approved cloud/KMS/object-storage/observability only: `AWS_*`, `GCP_KMS_KEY_NAME`, `GOOGLE_APPLICATION_CREDENTIALS`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN`.
- Deployment-specific public endpoints and allowed origins: `UCVE_WS_PUBLIC_URL`, `UCVE_CONTROL_PLANE_URL`, `UCVE_WORKER_WS_URL`, `WAVIA_CONTROL_PLANE_URL`, `UCVE_ALLOWED_ORIGINS`.

Keep `RUN_LIVE_PROVIDERS=0` and `RUN_LIVE_TELEPHONY=0` until the explicit H15 approval. Do not copy values from an old machine until they are still valid and appropriate for the new environment.

## 12. Working style and autonomy rule

- Work in small, atomic, reviewable task commits. Push clean phase checkpoints to `wavia-fixv1`; never force-push.
- Before risky multi-file work, make a rollback commit. Preserve unrelated dirty changes.
- Use failure-first focused tests, then related tests, then the phase close gate. Inspect diffs for secrets, privacy leaks, mock-success paths, tenant escape and protected-path changes.
- Save durable evidence: command, environment/safety mode, exit code, pass/fail/skip count, artifact path and known limits.
- Stop at explicit human gates. Do not treat silence as approval.
- Make ordinary technical decisions independently and document why. Ask Hamzi only for an irreversible action, live/paid traffic, deployment/publication, external coordination, a material product choice that changes scope, or contradictory evidence that cannot be resolved from checked-in sources.
- For every dashboard frontend task, first read `docs/DESIGN.md` and `docs/design/design-tokens.json`; use them as governing visual references. Do not invent a migration or treat a mock/dashboard value as live data.

## 13. Unverified at this handover

- No tests/builds/live services were rerun for this documentation-only handover.
- The recorded `fad38e8` branch state was checked after a fresh clone; its historical test results were not revalidated here.
- The exact operational status of any existing local Docker containers, `.env` files, credentials, WorkOS configuration and provider accounts is unverified.
- The new Ripple references intentionally conflict with the earlier Theme B visual pilot. Their migration scope, timing and acceptance criteria are unverified and must be resolved in an approved frontend task before visual implementation.
- Live vendor latency, carrier behavior, production deployment, shared migration, package publication, real-device/browser/accessibility coverage and final release qualification remain unverified as stated above.
