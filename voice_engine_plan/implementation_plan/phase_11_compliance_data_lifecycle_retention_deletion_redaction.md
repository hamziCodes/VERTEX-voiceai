# Phase 11: Compliance Data Lifecycle (Retention, Deletion, Redaction)

## 1. Executive Summary & Core Logic

Implement enforceable data lifecycle rules: retention windows, legal hold, tenant-initiated deletion, automated purge jobs, and text redaction **before** third-party LLM calls. Blueprint File 05 §9 places redaction immediately after recording capture and before extraction — PII must not transit to Groq/Gemini unless policy explicitly allows the field (e.g. insurance ID for VOB extraction). No legacy repo implements automated redaction (AUDIT_02: awaazlabs uses Clerk + UI mocks only). Depends on Phase 10 classification, Phase 08 storage split (JSONB + S3), Phase 07 PHI-safe logging.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `RedactionService` with field-purpose scoping | File 05 §9 — blanket strip breaks extraction |
| Scheduled purge worker (cron/K8s CronJob) | Deterministic retention enforcement |
| S3 lifecycle rules + app-level delete | Defense in depth for audio blobs |
| Soft-delete + hard-delete phases | GDPR erasure with audit trail (Phase 12) |

**Reference docs:** blueprint File 05 §1 sequence (Redact before Extract); GDPR Art. 17; HIPAA minimum necessary.

## 3. What / How / Why

- **What:**
  - `RedactionPolicy` per tenant (from Phase 10 tier + overrides): `redact_pii_in_transcript`, `pii_categories`, `retention_days`, `zero_retention_mode`
  - `RedactionService.redact_transcript(turns, policy) -> turns` — **regex-only v1** for phone/email/SSN patterns; field-purpose allowlist (e.g. keep `insurance_id` when extraction schema requires)
  - **Known limitation (documented):** regex redaction **does not catch names/addresses in Urdu/Arabic script** or other non-Latin text. NER is **off by default**. **Required checkpoint in Phase 15** — language registry must reference this gap; script-aware redaction is future work, not silently assumed.
  - **Storage columns:** `transcript_raw_encrypted` + `transcript_redacted` (dual columns). Zero-retention tenants **skip raw entirely**.
  - **Retention defaults:** standard=90 days, hipaa=2555 days, gdpr_strict=30 days — overridable per tenant contract in `tenant_compliance_profile.retention_days_override`
  - `RetentionScheduler`: **daily** purge job marks `sessions.purge_after`, deletes JSONB + S3 object when due
  - `LegalHold` flag on session/tenant blocks purge
  - `ErasureRequest` workflow: tenant admin triggers GDPR delete — cascades Postgres + S3 + Redis keys (Phase 17)
  - `RecordingRedaction`: **deferred** — audio bleeping flagged `[LATER]`; text redaction is day-one
- **How:** On session end (Phase 17 hook): apply redaction to transcript copy destined for extraction LLM; persist `transcript_redacted` always; persist `transcript_raw_encrypted` only when tier allows and not zero-retention. Purge job: daily cron deletes expired rows + S3 objects via Phase 08 client. Log purge counts via Phase 07 metrics (`ucve_purge_total`).
- **Why this approach:** Redact-after-extraction sends PHI to vendor APIs — unacceptable for HIPAA tenants. awaazlabs persisted Retell transcripts to Supabase without scrub (`legacy_codebases/awaazlabs/ali-Awaazlabs-client-dashboard-backend/supabase/functions/retell-webhook/index.ts`). Alternative: never store transcripts — rejected; post-call CRM (Phase 20) requires durable records with policy controls.

## Deliverables

- `core/compliance/redaction.py` — `RedactionService`, regex pattern library
- `core/compliance/redaction_policy.py` — `RedactionPolicy` model
- `core/compliance/redaction_limitations.md` — documents regex-only gap + Phase 15 dependency
- `core/compliance/retention.py` — `RetentionScheduler`, purge logic
- `core/compliance/erasure.py` — GDPR erasure orchestrator
- `core/compliance/legal_hold.py`
- `infra/db/migrations/005_retention_erasure.sql` — `transcript_raw_encrypted`, `transcript_redacted`, `purge_after`, `legal_hold`, `erasure_requests`
- `worker-jobs/purge_retention.py` — daily scheduled purge entrypoint
- `tests/fixtures/transcripts/phi_sample.json` — synthetic Latin-script only

## 4. Compute & Resource Profile (if applicable)

Text redaction: ~1–5 ms per turn (regex path); NER add-on optional +50 ms — **off by default**. Purge job: batch 1000 sessions/run daily; S3 delete ~100 ms/object. Storage reclaimed depends on tenant volume — plan 1 GB/1000 calls audio average.

## 5. Compliance Notes (if applicable)

Purges and erasures must emit Phase 12 audit events (`data.purge`, `data.erasure_complete`). Erasure is irreversible — require Phase 13 role `compliance_admin`. HIPAA: maintain audit log of who accessed PHI even after content purge (metadata retained per policy). Multilingual PHI in Arabic/Urdu script may pass regex redaction undetected until Phase 15+ enhancement — document in tenant-facing compliance notes for `hipaa` tier.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Storage:** dual columns; zero-retention skips raw.
2. **Retention defaults:** standard=90, hipaa=2555, gdpr_strict=30; per-tenant contract override supported.
3. **Purge frequency:** daily job.
4. **Regex limitation:** explicit; Phase 15 checkpoint required for script-aware follow-up.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_11_compliance_data_lifecycle.py`
- **Asserts:** phone/email redacted in transcript; allowlisted field preserved; zero-retention skips raw write; dual columns populated correctly for HIPAA fixture; purge deletes JSONB + invokes S3 mock; legal hold blocks purge; erasure cascades tenant artifacts.
- **Pass threshold:** 100% redaction + purge tests; no raw PHI in extraction-bound payload for HIPAA tier fixture.
- **Latency target:** redact 50-turn transcript < 100 ms.
