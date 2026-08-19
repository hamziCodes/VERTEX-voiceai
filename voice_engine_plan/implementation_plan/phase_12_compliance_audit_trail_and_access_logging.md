# Phase 12: Compliance Audit Trail and Access Logging

## 1. Executive Summary & Core Logic

Build an append-only, tamper-evident audit log for security-relevant and compliance-relevant actions: credential access, mint rejections, admin changes, PHI viewing, exports, config updates, and data lifecycle events. Harvests habiba `admin/audit.py` (`legacy_codebases/habiba-sdk-agent/admin/audit.py` — `record_mint_rejection`, `record_admin_action`) and awaazlabs dashboard audit event taxonomy (`legacy_codebases/awaazlabs/AwaazLabs-frontend-from-github/src/shared/audit.ts` — 12 frozen event types). Separate from Phase 07 debug logs — longer retention, stricter access, no PHI in `detail` JSON.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Append-only Postgres table | Habiba `mint_rejections` / `admin_audit_log` pattern |
| Autocommit separate connection for failure-path audits | habiba `record_mint_rejection` — must not roll back with failed mint txn |
| Immutable insert-only API | No UPDATE/DELETE on audit rows (DB trigger enforce) |
| Structured `detail` JSONB without PHI bodies | Store IDs and action metadata only |
| `on_audit_event` stub hook | Cheap now; full SIEM export `[LATER]`, unscheduled |

**Reference docs:** blueprint File 05 §9; habiba `control_plane/app.py` rejection logging; SOC2 CC7.2 monitoring.

## 3. What / How / Why

- **What:**
  - Tables: `audit_log` (general), `mint_rejections` (habiba-compatible), `credential_access_log` (Phase 09 resolves)
  - `AuditEvent`: `{id, tenant_id, actor_id, actor_type, action, resource_type, resource_id, detail, ip, user_agent, created_at}`
  - **Actor ID for HMAC-only path:** `{tenant_id}:{api_key_id}` when no human user (Phase 13 API keys)
  - `AuditAction` enum: superset of awaazlabs 12 types + platform actions: `session_mint`, `session_mint_rejected`, `credential_resolve`, `credential_rotate`, `agent_config_published`, `transcript_view`, `recording_access`, `data_export`, `data_purge`, `data_erasure`, `compliance_tier_change`, `api_key_create`, `api_key_revoke`, `provider_promote`, `quota_slot_released_stale`, `call_record_created`, `crm_dispatch`, `tool_call`, `tool_result`, `mcp_connect`, `tool_timeout_fallback`
  - `AuditWriter.record()` — never raises to caller on insert failure; logs WARNING via Phase 07 (habiba pattern: `admin/audit.py` lines 9–10)
  - **`on_audit_event(event)` stub hook** — register callbacks for future SIEM export; **no-op default in v1**; full SIEM wiring is `[LATER]`, unscheduled (not owned by Phase 25)
  - Query API: tenant-scoped for dashboard; **cross-tenant full read: `platform_admin` role only** (Phase 13)
- **How:** Instrument Phase 09 vault resolve/rotate, Phase 13 auth login, Phase 11 purge/erasure, Phase 20 exports. Mint rejections use separate autocommit conn (copy habiba `record_mint_rejection` design). DB trigger rejects UPDATE/DELETE on `audit_log`. Retention: 7 years default for HIPAA tenants (Phase 10 policy); 1 year standard — enforced by Phase 11 archival job (move to cold storage `[LATER]`).
- **Why this approach:** Compliance without audit trail fails customer security questionnaires. Debug logs (Phase 07) rotate quickly and may contain operational noise — not substitutable. awaazlabs audit is frontend-only local store — not durable server audit; UCVE requires server-side source of truth.

## Deliverables

- `infra/db/migrations/006_audit_log.sql`
- `core/compliance/audit/__init__.py`
- `core/compliance/audit/writer.py` — `AuditWriter`, `on_audit_event` hook registry
- `core/compliance/audit/actions.py` — `AuditAction` enum
- `core/compliance/audit/models.py` — `AuditEvent`
- `core/compliance/audit/queries.py` — read-only tenant-scoped + platform_admin cross-tenant queries
- `core/compliance/audit/triggers.sql` — immutability triggers (or in migration)
- `control-plane/audit_routes.py` — GET `/v1/audit` (auth Phase 13)

## 4. Compute & Resource Profile (if applicable)

Insert: ~2 ms row + index. Volume estimate: ~10 events/session + admin events — 100k sessions/month ≈ 1M rows/month (~500 MB with JSONB detail). Partition `audit_log` by month at scale (Phase 30). Hook dispatch: < 0.5 ms per registered callback.

## 5. Compliance Notes (if applicable)

Audit logs may reference PHI subjects by ID only — never transcript text in `detail`. Access to audit log itself is audited (meta-audit: `audit_log_view` action). HIPAA: audit log integrity controls documented for customer BAA pack.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **HMAC actor ID:** `tenant_id` + `api_key_id`.
2. **Cross-tenant visibility:** full read, `platform_admin` only.
3. **SIEM:** `on_audit_event` stub hook exists now; full SIEM export `[LATER]`, unscheduled — Phase 25 does not deliver it.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_12_compliance_audit_trail.py`
- **Asserts:** insert succeeds; UPDATE/DELETE blocked by trigger; mint rejection recorded on failed txn rollback; credential resolve creates row without secret; tenant A cannot query tenant B audit; `on_audit_event` callback invoked; writer failure does not break caller.
- **Pass threshold:** 100% immutability + isolation tests.
- **Latency target:** audit insert async fire-and-forget overhead < 1 ms caller-side.
