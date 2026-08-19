# Phase 25: Error Taxonomy and Alerting Strategy

## 1. Executive Summary & Core Logic

Define a unified error code taxonomy, structured error surfaces (WS `error` events, API responses, post-call dead-letter queue), and alerting routes for operational and tenant-facing notifications. Closes awaazlabs gaps: fire-and-forget background tasks (`p.catch(console.error)` AUDIT_02 §5), no retry on inter-service HTTP (AUDIT_02 §6), fail-open webhook secrets (fixed in Phase 21 but errors still need routing). Extends Phase 14 soft-cap warn (80%) into full alerting. Harvests metric/error **patterns** from v3/multilingual WS `error` events (AUDIT_01/03 §4) and habiba SDK `error` (AUDIT_04 §4) into one vocabulary aligned with File 8 §3.

Depends on Phase 07 logging/metrics, Phase 12 audit hooks, Phase 14 quota events, Phase 24 SLO breaches.

**Client surface policy:** **fully generic** messages to callers/SDK — no internals, no stack traces, **no PHI ever**; detail in logs and dashboard only. **DLQ retention:** **30 days** (Phase 11 alignment). **Alert channels v1:** **email + tenant webhook only** — no PagerDuty/Slack until on-call process exists.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `UCVEErrorCode` enum + HTTP mapping | Consistent client handling across SDK/API |
| Dead-letter queue (DLQ) in Postgres | awaazlabs swallowed errors → monitored queue |
| Severity tiers: `info`, `warn`, `error`, `critical` | Alert routing discrimination |
| Tenant webhook for ops alerts | Phase 14 80% warn expansion |
| Generic client message map | Caller-safe error surface |
| 30-day DLQ retention + sweeper | Matches `gdpr_strict` tier retention (30d), not the general default |

**Reference docs:** blueprint File 05 §6 (awaazlabs error handling gaps); File 08 §3 `error` event; File 09 §5 anti-patterns #8–10; habiba `60-RUNBOOK-CAP-EXHAUSTION.md`.

## 3. What / How / Why

- **What:**
  - `UCVEErrorCode` categories:
    - **Auth:** `AUTH_INVALID`, `AUTH_EXPIRED`, `QUOTA_EXCEEDED`
    - **Pipeline:** `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, `FSM_INVALID_TRANSITION`, `BARGE_IN_FAILED`
    - **Compliance:** `HIPAA_BAA_REQUIRED`, `DATA_CLASSIFICATION_BLOCKED`
    - **Telephony:** `WEBHOOK_SIGNATURE_INVALID`, `TRUNK_UNAVAILABLE`, `CALLER_ID_MISSING`
    - **Post-call:** `EXTRACTION_FAILED`, `DISPATCH_FAILED`, `REVIEW_REQUIRED`
    - **Internal:** `INTERNAL_ERROR` (opaque to client)
  - `StructuredError`: `{code, message, severity, correlation_id, retryable, details}` — maps to WS `{type: "error", code, message}`
  - **`ClientErrorMapper`:** maps any internal error to **generic caller-safe message** — e.g. `PROVIDER_TIMEOUT` → "We're having trouble right now. Please try again."; **`details` and `correlation_id` never sent on WS to end-user clients** (correlation_id available to host-backend integrators via separate debug header only when `UCVE_DEBUG_ERRORS=true`)
  - **`DeadLetterQueue`:** `{job_id, job_type, payload_ref, error_code, attempts, last_attempt_at, expires_at}` — **30-day TTL**; daily purge job (Phase 11 pattern)
  - **`AlertRouter`:** routes by severity — `warn` → Phase 07 metric + tenant optional webhook; `critical` → metric + Phase 12 audit + **email to tenant alert contacts**
  - **Alert channels v1:** `email` (SMTP/env config) + `tenant_webhook` (Phase 14-style HMAC) — **PagerDuty/Slack `[LATER]`**
  - **Quota soft warn (80%):** emit `QUOTA_SOFT_WARN` alert (Phase 14 decision)
  - **SLO breach:** consume Phase 24 warn events → `LATENCY_SLO_BREACH`
  - Error redaction: never include transcript/PHI in `details` (Phase 07)
- **How:** All services raise `UCVEError` subclass → middleware converts to `StructuredError`. WS pipeline sends **generic** `error` event before disconnect on fatal fault. Post-call worker on final failure → DLQ insert + alert. Control plane returns JSON `{error: StructuredError}` — public fields sanitized via `ClientErrorMapper`. AlertRouter v1: email + webhook implementations; log+metric always on.
- **Why this approach:** Four legacy repos used inconsistent error strings — SDK consumers cannot branch on prose. awaazlabs silent failures lose CRM data. **Exposing internals to callers rejected** — PHI leakage and social-engineering risk on live calls. 30-day DLQ aligns with **`gdpr_strict` tier retention (30d)** — not the general default across all tiers (Phase 11).

## Deliverables

- `core/errors/__init__.py`
- `core/errors/codes.py` — `UCVEErrorCode`, `UCVEError`
- `core/errors/structured.py` — `StructuredError`, WS/API mappers
- `core/errors/client_mapper.py` — generic caller-safe messages
- `core/errors/dlq.py` — `DeadLetterQueue` repo + 30-day retention
- `core/errors/alert_router.py` — `AlertRouter`, email + webhook channels
- `core/errors/redaction.py` — strip PHI from error details
- `infra/db/migrations/014_dead_letter_queue.sql`
- `control-plane/routes/alerts.py` — tenant alert webhook + email config
- `worker-jobs/dlq_retry_sweeper.py` — retry DLQ with backoff (max 3) + expiry purge

## 4. Compute & Resource Profile (if applicable)

DLQ insert: < 5 ms. Alert routing: < 1 ms (log path); email async queue. DLQ sweeper: O(pending) every 5 min — negligible at <10k/day failures. Error enum lookup: O(1).

## 5. Compliance Notes (if applicable)

DLQ payloads may reference PHI-bearing job IDs — store refs not raw transcript. Access DLQ via Phase 13 admin RBAC + Phase 12 audit. Alert webhooks must not include PHI in body — IDs and codes only. GDPR: DLQ entries subject to Phase 11 retention policy — **30-day DLQ TTL matches `gdpr_strict` tier default**, not the general default across all tiers. **Client-facing errors must never contain PHI** — enforced by `ClientErrorMapper` tests.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Client-visible internal errors:** **fully generic to caller** — opaque codes/messages; full detail logs/dashboard only; no PHI on WS.
2. **DLQ retention:** **30 days default** — aligned with **`gdpr_strict` tier (30d)**, not the general default; purge unless legal hold.
3. **Alert channel v1:** **email + tenant webhook only** — PagerDuty/Slack deferred until on-call process defined.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py`
- **Asserts:** each error code maps to HTTP status; WS error event uses generic message only; no PHI/internals in client payload; DLQ receives failed dispatch job; DLQ entry expires after 30 days fixture; retry sweeper respects max attempts; quota soft warn fires AlertRouter; correlation_id present in server logs not WS client frame.
- **Pass threshold:** 100% taxonomy + DLQ tests.
- **Latency target:** error serialization < 1 ms p99.
