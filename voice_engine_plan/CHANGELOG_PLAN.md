# Voice Engine Plan — Revision Log

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
