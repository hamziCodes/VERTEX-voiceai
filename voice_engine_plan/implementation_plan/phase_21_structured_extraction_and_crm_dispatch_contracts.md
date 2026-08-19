# Phase 21: Structured Extraction and CRM Dispatch Contracts

## 1. Executive Summary & Core Logic

Implement schema-driven post-call extraction, verification, summarization, and idempotent CRM/webhook dispatch — generalizing awaazlabs Groq extraction (`legacy_codebases/awaazlabs/ali-Awaazlabs-client-dashboard-backend/supabase/functions/transcript-crm-poc/extraction.ts`, `transcript-vob-poc/`) and WhatsApp notify pattern (`_shared/messaging.ts` Green API). Uses Phase 06 `FailoverRouter` for LLM extraction (not Groq-only — fixes awaazlabs lock-in AUDIT_02 §5). Webhooks **fail closed** if shared secret unset (fixes awaazlabs Retell `checkSecret` fail-open AUDIT_02 §6). Depends on Phase 20 `CallRecord`, Phase 11 redacted transcript input, Phase 10 HIPAA BAA gate for cloud LLM.

**Human review queue** stub for low-confidence extractions. **WhatsApp** interface stub only (consistent with Phase 19 Twilio treatment).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `TenantExtractionSchema` JSON Schema registry | File 05 §3 — domain-agnostic |
| Phase 06 LLM router for extraction | Sovereignty + failover |
| HMAC-signed webhook payloads | awaazlabs pattern improved — fail closed |
| Idempotency keys on dispatch | Fix awaazlabs false-success (`save-booking/index.ts:15–16`, AUDIT_02 §6) |
| Retry with exponential backoff | awaazlabs had no retry (AUDIT_02 §5–6) |
| Per-tenant schema field cap | Prevents runaway prompt/compute |

**Reference docs:** blueprint File 05 §3–6; awaazlabs `retell-webhook/index.ts` event flow.

## 3. What / How / Why

- **What:**
  - `TenantExtractionSchema`: tenant-authored fields (dental, real estate, etc.) — File 05 examples; **`max_fields` per tenant** (default **50**, overridable on schema — validated at publish by Phase 26 `AgentConfigValidator`, not hardcoded constant)
  - `ExtractionService.extract(transcript, schema) -> dict` — LLM structured output; null not invented
  - `VerificationService.verify(extracted, schema, tenant_id) -> list[VerificationIssue]` — E.164 phones, timezone-aware dates (awaazlabs `appointment-time.ts` + `retell-webhook/index.ts:378–381` UTC vs clinic zone lesson); low-confidence fields flagged
  - **`HumanReviewQueue` stub:** `{issue_id, call_id, field_path, confidence, status: pending|approved|rejected}` — persisted queue for Phase 27 UI; low-confidence extractions land here instead of silently shipping to CRM
  - `SummarizationService.summarize()` — executive summary + sentiment trajectory `[NEW]` vs awaazlabs extraction-only
  - `WebhookDispatcher.dispatch(target, payload, idempotency_key)` — HMAC sign, retry 3x, fail closed without secret
  - **`WhatsAppDispatcher` interface stub** — config types + ABC only; no Green API implementation (matches Twilio Media Streams stub pattern)
  - `FollowUpTrigger` stub — SMS/WhatsApp channel config `[LATER]` full impl
  - CRM payload: `{call_id, tenant_id, extracted, verified, summary, disposition, idempotency_key}`
- **How:** Phase 20 enqueue triggers async worker (`post-call/worker.py`). Input: **Phase 11 redacted transcript** only unless HIPAA BAA ack + field-purpose allowlist permits raw fields. Extraction via Phase 06 LLM chain. Verification issues + low-confidence fields → `HumanReviewQueue`. Dispatch targets from **Phase 21 `webhook_targets` registry** only after review gate passes (or auto-approve above confidence threshold). Success requires HTTP 2xx **and** persistence confirmation — no awaazlabs false-success. Phase 12 audit: `data_export`, `crm_dispatch`. Phase 14 `extraction_calls` meter increment.
- **Why this approach:** Enterprises buy outcomes (appointment booked, lead captured). awaazlabs proved extraction shape for dental but hardcoded clinic + Retell + Groq-only. UCVE tenant schema makes vertical reusable. Human review stub prevents bad CRM data at scale. Alternative: human review queue only — insufficient for automation; silent ship — unacceptable.

## Deliverables

- `post-call/extraction/schema.py` — `TenantExtractionSchema`, per-tenant `max_fields`
- `post-call/extraction/service.py` — `ExtractionService`
- `post-call/verification/service.py` — `VerificationService`
- `post-call/verification/phone.py` — E.164 normalize
- `post-call/verification/datetime.py` — timezone rules
- `post-call/review/queue.py` — **`HumanReviewQueue` stub**
- `post-call/summarization/service.py`
- `post-call/webhook/dispatcher.py` — HMAC, retry, idempotency
- `post-call/webhook/targets.py` — tenant webhook registry
- `post-call/channels/whatsapp.py` — **interface stub only**
- `post-call/worker.py` — async job processor
- `infra/db/migrations/012_extraction_schemas_webhooks.sql` — includes review queue table
- `control-plane/routes/extraction_schemas.py` — CRUD stub (auth Phase 13)

## 4. Compute & Resource Profile (if applicable)

Extraction LLM call: 1–3 s (async, post-call — not latency critical). Verification: < 50 ms. Webhook dispatch: < 500 ms per target; retries add backoff. Worker concurrency: 10 jobs/worker recommended. Schema field cap enforced at publish — O(1).

## 5. Compliance Notes (if applicable)

Extraction sends redacted transcript to LLM — Phase 10 subprocessor + BAA check. Webhook payloads must not include raw audio URLs for GDPR strict without consent flag. Failed dispatch retains record for manual retry — Phase 12 audit. PHI fields in extracted JSON follow Phase 11 retention on `CallRecord`. Human review queue access RBAC-scoped (Phase 13).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Human review queue:** **stub now** — low-confidence extractions land in queue; UI in Phase 27.
2. **WhatsApp/Green API:** **interface stub only** — consistent with Phase 19 Twilio stub pattern.
3. **Max extraction schema fields:** default **50**, **per-tenant configurable** on extraction schema — **validated at publish by Phase 26** — not hardcoded.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py`
- **Asserts:** extraction returns null for missing fields; phone normalized E.164; invalid date flagged; low-confidence field enqueued to HumanReviewQueue; webhook HMAC verified by receiver mock; missing secret fails closed; idempotent retry does not duplicate; verification catches awaazlabs-style false-success; HIPAA blocks extraction LLM without BAA ack; schema rejects >max_fields; WhatsAppDispatcher is abstract stub.
- **Pass threshold:** 100% extraction+dispatch unit tests; end-to-end fixture call → webhook received once after review gate.
- **Latency target:** full post-call worker path < 10 s p95 (excl. LLM).
