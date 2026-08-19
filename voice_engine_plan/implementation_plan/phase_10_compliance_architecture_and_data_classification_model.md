# Phase 10: Compliance Architecture and Data Classification Model

## 1. Executive Summary & Core Logic

Establish the platform-wide compliance taxonomy: what data classes exist, which artifacts carry PHI/PII, how each class may be stored/transmitted/logged, and how tenant compliance tiers override defaults. None of the four legacy voice repos implement automated compliance classification (AUDIT_05 §3); awaazlabs relied on Clerk role-gating and UI mock fixtures (`legacy_codebases/awaazlabs/AwaazLabs-frontend-from-github/src/mock/`) rather than data-level controls. This phase defines the **data dictionary and policy engine** that Phases 11–12 enforce. Depends on Phase 08 schema (`tenant_compliance_profile`) and Phase 07 logging rules.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Pydantic policy models in `core/compliance/` | Type-safe, versionable; referenced by worker, control plane, post-call |
| Enum-driven classification | Avoid string drift across services |
| Policy-as-data in Postgres JSONB | Tenant overrides without code deploy |
| Explicit BAA subprocess registry | HIPAA requires knowing which Tier-2 vendors receive PHI |

**Reference docs:** blueprint File 05 §9 (`ComplianceTier`, `RedactionPolicy`); HIPAA Security Rule summaries; GDPR Art. 5/17/32; habiba `tenants.status` suspend pattern — `legacy_codebases/habiba-sdk-agent/supabase/migrations/0001_schema.sql`.

## 3. What / How / Why

- **What:**
  - `DataClass` enum: `public`, `internal`, `pii`, `phi`, `credentials`, `audit`
  - `ArtifactType` enum: `raw_audio`, `transcript_turn`, `recording_object`, `llm_prompt`, `llm_response`, `extraction_output`, `usage_event`, `audit_log`, `provider_payload`
  - `ComplianceTier`: `standard`, `hipaa`, `gdpr_strict`, `pci_dss` (**`pci_dss` reserved — out of scope until payment flows exist**)
  - `DataClassificationRegistry`: maps `(ArtifactType, field_path) -> DataClass`
  - `CompliancePolicy`: per-tier rules — `{allow_cloud_llm: bool, allow_cloud_stt: bool, require_baa: bool, min_retention_days, max_retention_days, encryption_required: bool}`
  - `TenantComplianceProfile` stored in Phase 08 table; loaded at session mint
  - `SubprocessorRegistry`: list of Tier-2 vendors (Gladia, Groq, etc.) with `{name, data_classes_sent, baa_available, regions}`
- **How:** Worker and control plane call `classify(artifact, field)` before persist/log/export. **New tenants default to `standard` tier**; `hipaa` set explicitly at onboarding/sales workflow. Tier defaults ship in `core/compliance/defaults/` YAML; tenant JSONB overrides specific flags only (not entire policy replacement without admin audit — Phase 12). **HIPAA cloud LLM gate:** raw transcript to non-BAA cloud LLM blocked unless `tenants.hipaa_baa_acknowledged_at` timestamp is set (signed acknowledgment). HIPAA tier: blocks persistence of raw audio to non-BAA object storage; requires encryption flags on Postgres columns marked `phi`. GDPR strict: requires lawful basis flag on tenant (`lawful_basis: contract|consent|legitimate_interest`).
- **Why this approach:** Compliance cannot be a post-call checklist — classification must precede Phase 17 pipeline writes. awaazlabs' UI-only PHI gating (`legacy_codebases/awaazlabs/AwaazLabs-frontend-from-github/src/shared/audit.ts` documents dashboard audit events but not storage policy) is insufficient for healthcare B2B. Alternative: per-tenant custom code paths — rejected; policy engine keeps one codebase.

## Deliverables

- `core/compliance/__init__.py` (replaces Phase 00 placeholder)
- `core/compliance/classification.py` — `DataClass`, `ArtifactType`, registry
- `core/compliance/tiers.py` — `ComplianceTier`, `CompliancePolicy`
- `core/compliance/tenant_profile.py` — `TenantComplianceProfile` loader
- `core/compliance/subprocessors.yaml` — vendor registry template
- `core/compliance/defaults/standard.yaml`
- `core/compliance/defaults/hipaa.yaml`
- `core/compliance/defaults/gdpr_strict.yaml`
- `infra/db/migrations/004_compliance_profile_extend.sql` — extend Phase 08 profile columns + `hipaa_baa_acknowledged_at`
- `docs/compliance/DATA_DICTIONARY.md` — field-level classification reference

## 4. Compute & Resource Profile (if applicable)

Classification lookup: O(1) dict — < 0.01 ms per field. Policy load cached per tenant (TTL aligns with Phase 09 secret cache: 5–15 min). Subprocessor registry static at boot (~5 KB).

## 5. Compliance Notes (if applicable)

This phase **is** compliance architecture. Output artifacts (`DATA_DICTIONARY.md`, policy YAML) are themselves compliance evidence for customer security reviews. Do not store sample PHI in repo fixtures — use synthetic tokens (`[REDACTED_NAME]`).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **PCI-DSS tier:** enum reserved; out of scope until payment flows.
2. **Default tenant tier:** `standard`; `hipaa` set explicitly at onboarding.
3. **HIPAA cloud LLM:** require `hipaa_baa_acknowledged_at` before raw transcript to cloud LLM.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_10_compliance_architecture.py`
- **Asserts:** every `ArtifactType` has classification entries; HIPAA tier denies non-BAA subprocessor for `phi`; tenant override merges correctly; unknown field defaults to `pii` (fail-safe); policy load from Phase 08 mock row.
- **Pass threshold:** 100% registry coverage; zero unclassified required fields.
- **Latency target:** classify 1000 fields < 10 ms total.
