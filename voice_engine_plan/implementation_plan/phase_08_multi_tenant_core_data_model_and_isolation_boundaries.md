# Phase 08: Multi-Tenant Core Data Model and Isolation Boundaries

## 1. Executive Summary & Core Logic

Define the Postgres schema and application-level isolation boundaries for tenants, agents, sessions, usage, and quotas — decided early before dashboard or SDK work. Harvests habiba table shapes (`legacy_codebases/habiba-sdk-agent/supabase/migrations/0001_schema.sql`) but targets **self-managed PostgreSQL** (not Supabase) for BAA/compliance flexibility with healthcare clients. Row-Level Security (RLS) enforced at DB layer; every query scoped by `tenant_id`. **Phase 09 credential vaulting depends on this phase's `tenants` table** — Phase 08 does not build on Phase 09.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Self-managed PostgreSQL 15+ | Not Supabase — avoids vendor lock-in; full BAA control for HIPAA tenants |
| SQL migrations (`infra/db/migrations/`) | Versioned, reviewable; habiba Supabase migrations as reference |
| UUID primary keys | habiba `tenants`, `agents`, `sessions` |
| RLS policies per table | `tenant_id = current_setting('app.tenant_id')` pattern from habiba `worker/config.py` |
| SQLAlchemy 2.0 async ORM (optional) | Type-safe repos; raw SQL acceptable for migrations |

**Reference docs:** blueprint File 01 §3.3; habiba `0001_schema.sql`; AUDIT_04 §3 handshake/state.

## 3. What / How / Why

- **What:** Core tables — `tenants` (includes `allowed_origins TEXT[]`, `key_tier ENUM('platform','byok')`, `allow_testing_providers BOOL DEFAULT false`), `agents`, `agent_provider_config` (JSONB), `sessions` (includes `config_version_id UUID` pin + `pinned_at TIMESTAMPTZ` from Phase 26 mint), `session_transcripts` (JSONB structured turns + metadata), `session_recordings` (S3 URI pointer + checksum), `usage_events`, `quota_state`, `tenant_compliance_profile`. **Storage split:** queryable transcript fields (text, timestamps, speaker, language) in Postgres JSONB; raw audio and large blobs in S3-compatible object storage (`s3://{bucket}/{tenant_id}/{session_id}/recording.wav`) referenced by URI in `session_recordings`. **Webhook dispatch targets** live in Phase 21 (`webhook_targets` table) — not Phase 08. Indexes on `(tenant_id, started_at)`, `(tenant_id, at)` for usage. Foreign keys cascade on tenant delete. Application repos require `tenant_id` on every read/write.
- **How:** Migrations run against self-managed Postgres (Docker Compose locally per Phase 30). Control plane sets `app.tenant_id` per connection (habiba pattern: `legacy_codebases/habiba-sdk-agent/worker/config.py` RLS session var). Workers load agent config via tenant-scoped query only. Cross-tenant reads fail closed. Extend habiba session model with `transport_type`, `degraded_flags`, `compliance_tier`.
- **Why this approach:** v3/MULTI had zero tenancy (AUDIT_01/03 §5). Retrofitting RLS after UI exists is expensive. Alternative: schema-per-tenant — rejected for operational cost at SaaS scale.

## Deliverables

- `infra/db/migrations/001_core_tenant_schema.sql` — includes `tenants.allowed_origins`, `tenants.key_tier`, `tenants.allow_testing_providers`, `sessions.config_version_id`, `sessions.pinned_at`
- `infra/db/migrations/002_rls_policies.sql`
- `core/db/__init__.py`
- `core/db/models.py` — SQLAlchemy models or Pydantic record types
- `core/db/session.py` — async engine + tenant-scoped session factory
- `core/db/repos/tenant_repo.py`
- `core/db/repos/agent_repo.py`
- `core/db/repos/session_repo.py`
- `core/db/repos/usage_repo.py`
- `core/db/repos/recording_repo.py` — S3 URI + metadata CRUD
- `core/storage/s3_client.py` — S3-compatible upload/download wrapper
- `infra/db/seed/dev_tenant.sql` — local dev seed (non-production)

## 4. Compute & Resource Profile (if applicable)

Postgres: 2 vCPU / 4 GB RAM handles ~100 tenants / 50 concurrent sessions for dev. Session row ~2 KB; transcript JSONB ~10–50 KB per call. `usage_events` append-only — plan partition by month at >10M rows (Phase 30).

## 5. Compliance Notes (if applicable)

Schema must support compliance tiers from day one: `tenant_compliance_profile.compliance_tier` ∈ `{standard, hipaa, gdpr_strict}` (placeholder enums). PHI columns: `session_transcripts`, future recording URLs — mark in data dictionary. Encryption at rest: Postgres provider responsibility + application-level field encryption for secrets (Phase 09). Tenant delete cascades with soft-delete option flagged for Phase 11.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Database host:** self-managed Postgres (not Supabase).
2. **Transcript storage:** JSONB in Postgres for structured/queryable fields; S3-compatible object storage for raw audio and large payloads.
3. **Provider config shape:** JSONB on `agents` / `agent_provider_config` (Phase 06 chains); normalize later if needed.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_08_multi_tenant_data_model.py`
- **Asserts:** migrations apply cleanly; RLS blocks cross-tenant SELECT; cascade delete tenant removes agents/sessions; usage_events append-only constraint; repo methods reject missing tenant_id.
- **Pass threshold:** 100% RLS isolation tests with two synthetic tenants.
- **Latency target:** tenant-scoped agent load < 10 ms p99 on local Postgres.
