# Voice Engine Plan — Revision Log

## 2026-08-21 — Core Voice Engine Phase 08–17 Execution Complete

- Executed and validated Phases 08 through 17 deliverables, test suites, and integrity checks:
  - **Phase 08:** Multi-tenant core data model (`002_multi_tenant_schema.sql`, `TenantContext`, `TenantIsolationMiddleware`).
  - **Phase 09:** Tenant credential vaulting (`003_tenant_credentials.sql`, `SecretVault`, `EnvelopeEncryption`, KMS backends).
  - **Phase 10:** Compliance classification model (`004_compliance_profile_extend.sql`, HIPAA/GDPR/Standard YAML profiles, `DATA_DICTIONARY.md`).
  - **Phase 11:** Compliance data retention & erasure (`005_retention_erasure.sql`, dual transcript columns, `RedactionService`, `LegalHoldManager`).
  - **Phase 12:** Compliance audit trail (`006_audit_log.sql`, DB triggers blocking UPDATE/DELETE, `AuditWriter`, RBAC isolation).
  - **Phase 13:** Dashboard/API/SDK AuthN/AuthZ (`007_auth_rbac.sql`, `NonceStore`, HMAC mint, JWT roomJoin tokens, 5-role RBAC, sliding window rate limit).
  - **Phase 14:** Metering & tenant quotas (`008_usage_quota_extend.sql`, `QuotaEnforcer` 80%/100% caps, 2-min heartbeat sweeper).
  - **Phase 15:** Multilingual registry & routing (`en`, `ur`, `ar`, `ms` profiles, `LanguageRouter` MULTI 3-word switch, `RTLVoiceValidator`).
  - **Phase 16:** Text normalization & pronunciation (`TextNormalizer`, numeral conversion, `SentenceChunker` TTFT 2-word first chunk, `RegenerationManager`).
  - **Phase 17:** Real-time orchestration pipeline (`PipelineOrchestrator`, `NativeWebSocketTransport`, `SileroVADAdapter`, `RedisSessionStore`, `RECONNECT_SCOPE.md`).
- Structural integrity script `verify_plan_integrity.py` verified 36/36 phases OK. All code committed & pushed to branch `hamza`.

## 2026-08-21 — Production Foundation Hardening (H0–H6) program opened

- Added `implementation_plan/HARDENING_FOUNDATION.md` (checklist + `FOUNDATION_READY` acceptance matrix).
- `EXECUTION_TRACKER.md`: `FOUNDATION_HARDENING: IN_PROGRESS`; phases **18–35** reset to `PENDING` / **BLOCKED** until `FOUNDATION_READY`.
- Packaging: uv workspace members `core`, `control_plane`, `worker_raw` (underscore dirs); hyphen path stubs retained for Phase 00 layout checks only.
- Docker COPY/CMD aligned to `control_plane` / `worker_raw`; `.env.example` expands auth/KMS/provider contract with production fail-closed boot.
- **H1:** PyJWT HS256 verify; Redis-capable nonce/rate limit; mint IDOR/origin/quota/UUID session + `ws_url`; platform dummy keys removed; LocalDev/OIDC fail-closed in production; `tests/hardening/test_h1_auth_crypto.py`.
- **H2:** `control_plane/app.py` routes (health/session/refresh/usage/audit/secrets/metrics); worker `/ws/audio` + 20s ping; real `NativeWebSocketTransport` send; `tests/hardening/test_h2_http_ws.py`.
- **H3:** `infra/db/migrate.py` + `009_foundation_hardening.sql`; parameterized `set_config`; Redis session store; shared audit writer/queries; AWS/GCP/Vault KMS fail-closed; pg tenant/session repos; `tests/hardening/test_h3_persistence.py` (live PG skipped without `DATABASE_URL`).
- **H4:** HIPAA override cannot enable cloud LLM without BAA; erasure refuses no-op; purge job deletes fixtures; `tests/hardening/test_h4_compliance.py`.
- **H5:** Gladia/Groq/Uplift adapters (mock without keys); Silero ONNX+energy; orchestrator multi-turn + barge cancel; AudioWorklet demo + host-backend mint; algorithmic EN numerals.
- **H6:** `tests/hardening/` suite (incl. anti-patterns) green; `docs/runbooks/FOUNDATION_READY.md` checklist. `FOUNDATION_READY` still blocked on compose/demo manual verify.

## 2026-08-20 — Cross-phase reconciliation (14 findings + §6 flags)

- Phase 06 ↔ 24: latency demotion owned by Phase 24 `SLOPolicy` (warn-only; `enforce_demotion` opt-in; rolling p50; N=5).
- Phase 12: expanded `AuditAction` enum; `on_audit_event` stub now; full SIEM `[LATER]` unscheduled (not Phase 25).
- Phase 08: added `allowed_origins`, `key_tier`, `allow_testing_providers`, `config_version_id`/`pinned_at`; webhook targets → Phase 21.
- Phase 01: added `control.pong`, `control.playback_started` to `ControlEvent` union.
- Phase 03/17/20/21/22/27: redaction, PostCallPipeline, max_fields, mcp_servers, RBAC citations reconciled.
- Phases 01–04 §6 rewritten to resolved decisions (aligned with EXECUTION_TRACKER).

## 2026-08-20 — Stage 2 complete (phases 00–35)

- Batch 4 approved (phases 15–21); Phase 20 `caller_id` (E.164) added to `CallRecord`.
- Batch 5 decisions applied (phases 22–28): MCP HTTP/SSE + 3s timeout + serial; RAG tier embedder + conservative speculative; SLO warn-only + client playback; generic errors + 30d DLQ; autosave + config pin; standalone Studio SPA; Flutter roadmap + LiveKit separate package + self-hosted OpenAPI.
- Phases 29–35 completed autonomously: developer docs, deployment, scaling, security, E2E matrix, runbooks, plan finalization.
- Generated `voice_engine_plan/README.md`, integrity script, updated both trackers.
