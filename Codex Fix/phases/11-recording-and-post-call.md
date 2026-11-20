# Phase 11 — Recording, Transcripts, and Post-Call Intelligence

**Status:** COMPLETE — 11A–11D VERIFIED OFFLINE

**Goal:** Persist honest call records and execute extraction, verification, human review, summaries, webhooks, retention, and erasure through durable jobs.

**Depends on:** Phase 09. Integrates Phase 10 tool/data schemas where relevant.

**Audit coverage:** F06, F11, I08 extraction, I09, I10, I13 post-call.

## Approved privacy and product policy

H11 was resolved by Hamzi on 2026-10-26 with authority to adapt the safest practical defaults for operators and callers.

- Recording is **off by default**. It starts only when the tenant explicitly enables it and the session records caller consent. Lack of consent is `not_requested`, never an error or a fabricated URI.
- Recording lifecycle is explicit: `not_requested`, `recording`, `available`, or `failed`. Only `available` may carry a verified object reference, checksum, channel count, duration, and region.
- Standard defaults retain redacted transcripts and post-call results for 30 days and consented recordings for 7 days. Tenants may choose shorter values. Longer or regulated schedules require an explicit reviewed tenant policy rather than a compliance-tier guess.
- `gdpr_strict` defaults to zero retained transcript/recording after required processing. HIPAA never implies that a call must be recorded; cloud processing still requires the existing BAA gate.
- Protected deployments require an allowed storage region in the tenant policy. Missing or unavailable regions fail closed; data never silently moves to another region.
- Summaries and extraction drafts may complete automatically. Any uncertain, sensitive, high-risk, or target-configured external side effect waits for human approval. Rejection is terminal for that dispatch, and approval is auditable and idempotent.
- Local tests use generated transcripts, fake HTTP endpoints, and bounded filesystem objects. A real webhook, cloud bucket, shared migration, provider, or call remains separately approved.

## Architecture decision

PostgreSQL is the source of truth for call state, incremental turns, policy snapshots, post-call jobs, extraction evidence, review decisions, and webhook attempts. Workers claim jobs with leases and idempotency keys; process memory is never the production queue. Recording bytes use a region-aware object-store interface and a bounded local adapter for tests. The realtime worker performs only small idempotent writes and never runs extraction, summary generation, delivery, or retention work inline.

Alternatives rejected:

- Redis/list-only post-call state cannot provide restart-safe completion or erasure proof.
- A compliance-tier recording default incorrectly treats HIPAA as a recording requirement and can violate caller expectations.
- Automatic webhook delivery on syntactically valid output ignores confidence, sensitivity, and operator review requirements.

## Files and interfaces

- Modify: session lifecycle to capture accurate start/end/transport/provider/usage and recording availability.
- Implement: object storage adapter, durable post-call queue/worker/retry/DLQ, extraction and webhook repositories.
- Modify: redaction/logging/audit/retention/erasure services.
- Test: persistence/restart, actual/no recording, extraction evidence, review gate, webhook replay, retention and erasure.

## Tasks

- [x] Create the call record at admission with real start time; finalize idempotently with end/disposition/metrics.
- [x] Never manufacture recording URI/dual-channel metadata. Store `not_requested`, `recording`, `available`, or `failed` state with evidence.
- [x] Persist transcript turns incrementally so provider/post-call failures do not erase the conversation.
- [x] Replace process-list enqueue with durable queue/outbox, retries, DLQ, leases and idempotency.
- [x] Replace fabricated extraction/summary/sentiment with schema-valid model/provider output plus source evidence/confidence; missing stays null.
- [x] Route configured/high-risk actions through human review before webhook/CRM dispatch.
- [x] Implement real HTTP webhook delivery with HMAC, timeout/backoff/idempotency and stored attempt/result.
- [x] Apply recursive privacy redaction; remove transcript previews/vendor response bodies from default logs.
- [x] Implement object deletion, legal hold, retention jobs and async-safe erasure across DB/storage/queues/audit. Failed partial erasure remains failed and retryable.
- [x] Test restart, duplicate finalize/job/webhook, extraction invalid JSON, missing review, storage failure, legal hold, and complete tenant erasure.

## Implementation sequence

Each checkpoint begins with failing tests, ends with focused regression and static checks, and receives its own commit and evidence file.

### 11A — Truthful durable call, transcript, and recording state

**Create/modify:**

- `infra/db/migrations/024_post_call_runtime.sql`
- `post_call/models/{call_record,recording,policy}.py`
- `core/db/repos/post_call_repo.py`
- `post_call/pipeline/{assembler,enqueue}.py`
- `worker_raw/orchestration/pipeline.py`
- `tests/post_call/test_call_lifecycle.py`
- `tests/db/test_phase11a_live_integration.py`

**Contract:** `PostCallRepository.start_call(...)` creates one call at admission with the real UTC start and an immutable policy snapshot; `append_turn(...)` stores an idempotent ordinal immediately; `finalize_call(...)` sets end/disposition/provider/usage/recording state exactly once without overwriting an existing final result. No recording object reference exists unless upload evidence exists. Tenant RLS and session uniqueness are enforced in PostgreSQL.

**Completed:** implementation commit `2287665`; evidence: [`../evidence/phase-11a/VERIFICATION.md`](../evidence/phase-11a/VERIFICATION.md). Full offline, focused, disposable PostgreSQL, formatting, type, compile, integrity, protected-path, and secret-literal gates passed. Next checkpoint: 11B.

### 11B — Durable jobs, evidence-backed intelligence, and review

**Create/modify:**

- `post_call/jobs/{models,repository,worker}.py`
- `post_call/extraction/{provider,service}.py`
- `post_call/summarization/{provider,service}.py`
- `post_call/review/{models,repository,policy}.py`
- `post_call/worker.py`
- `tests/post_call/test_durable_jobs.py`
- `tests/post_call/test_intelligence.py`
- `tests/post_call/test_review_policy.py`

**Contract:** a transactionally created outbox job is leased with bounded attempts, exponential retry, and DLQ terminal state. Extraction and summary accept only schema-valid provider JSON and persist source turn IDs plus confidence; absent or invalid output remains null/failed rather than invented. Review policy blocks sensitive/high-risk/uncertain/configured dispatch until an authenticated approval exists.

**Completed:** implementation commit `b510e8d`; evidence: [`../evidence/phase-11b/VERIFICATION.md`](../evidence/phase-11b/VERIFICATION.md). Focused, compatibility, full forced-offline, disposable PostgreSQL restart/RLS, Ruff, scoped strict mypy, compile, integrity, protected-path, and credential-literal gates passed. Next checkpoint: 11C.

### 11C — Real, bounded, replay-safe webhook delivery

**Create/modify:**

- `post_call/webhook/{models,repository,policy,dispatcher}.py`
- `post_call/jobs/worker.py`
- `tests/post_call/test_webhook_delivery.py`
- `tests/db/test_phase11c_live_webhook.py`

**Contract:** enabled tenant targets hold a credential reference rather than a raw secret. Delivery resolves the secret server-side, permits reviewed HTTPS destinations only, applies the existing private-network/redirect protections, signs canonical bytes, uses explicit connect/read/total deadlines, stores every safe attempt, and treats one `(tenant, target, call, event)` key as one logical delivery across retries.

**Completed:** implementation commit `b64a8fe`; evidence: [`../evidence/phase-11c/VERIFICATION.md`](../evidence/phase-11c/VERIFICATION.md). Focused, compatibility, full forced-offline, disposable PostgreSQL restart/RLS, Ruff, scoped strict mypy, compile, integrity, protected-path, and credential-literal gates passed. Migration 012's unused raw-secret table is isolated from the new runtime; its gated data migration/removal is part of 11D. Next checkpoint: 11D.

### 11D — Privacy, retention, erasure, and phase close

**Create/modify:**

- `core/compliance/{redaction,retention,erasure}.py`
- `core/storage/post_call_objects.py`
- `worker_jobs/purge_retention.py`
- `tests/compliance/test_phase11_privacy.py`
- `tests/post_call/test_recording_storage.py`
- `tests/e2e/scenarios/test_post_call_e2e.py`
- Phase 11 evidence and trackers

**Contract:** recursive redaction covers nested structured logs without retaining transcript previews or vendor bodies; retention claims success only after database and object deletion; legal hold blocks every deletion layer; tenant erasure is async-safe, restartable, and reports partial failure until all registered stores, jobs, attempts, and audit-safe tombstones complete.

#### 11D-1 — Recursive redaction and fail-closed retention contracts

**Completed:** implementation commit `2ce9e75`; evidence: [`../evidence/phase-11d1/VERIFICATION.md`](../evidence/phase-11d1/VERIFICATION.md).

- One bounded recursive sanitizer now covers transcript structures, structured-log extras, and error details, including nested sequences, sensitive keys, PII strings, authentication query values, binary data, and hostile depth.
- Transcript sanitization returns a new structure and does not mutate the source turns.
- Retention validates aware timestamps and non-negative schedules, records a safe result for every candidate, blocks held sessions before deletion, and reports success only after every required object/record deletion returns without failure.
- Object-store and record-delete errors produce stable reason codes without retaining exception text.
- The legacy in-memory purge fixture remains compatible, while durable object stores, database claims, restartable erasure, and legacy-secret migration remain 11D-2.

#### 11D-2 — Durable deletion, erasure, legacy migration, and phase close

**Completed:** implementation commit `a854b9e`; evidence: [`../evidence/phase-11d2/VERIFICATION.md`](../evidence/phase-11d2/VERIFICATION.md).

- Region-bound local and S3-compatible recording stores enforce size, suffix, tenant/session key, bucket, prefix, and region boundaries.
- PostgreSQL privacy jobs use leases, retries, stable request keys, per-object checkpoints, and a final database-deletion checkpoint.
- Legal hold is checked before object deletion and again inside the database transaction.
- Retention timestamps are captured during finalization; due calls can be enqueued without realtime-path deletion work.
- Tenant erasure removes operational tenant data, preserves immutable audit evidence, and leaves a scrubbed soft-deleted tenant tombstone.
- Quarantined legacy webhook rows are disabled, leased one at a time, encrypted into the tenant vault, replaced with a pending reviewed target, and cleared only after the encrypted write succeeds.
- Disposable PostgreSQL verification proved migration idempotency, restart recovery, raw-secret removal, encrypted storage, erasure, audit preservation, and cross-tenant RLS.
- No shared database migration or destructive production-data operation was run.

## Verification

```powershell
python -m pytest tests/post_call tests/compliance tests/e2e/scenarios/test_post_call_e2e.py -q
```

Expected: durable exactly-once logical outcome under retries; accurate timestamps/recording state; no fabricated summaries; review blocks configured action; erasure reports complete only when all stores succeed.

## Human intervention

H11 is resolved. A real webhook destination, cloud bucket, shared database migration, or production retention run is a separate live integration approval.

## Exit criteria

- Post-call work survives process restart.
- Dashboard/API can distinguish pending, succeeded, reviewed and failed outcomes.
- Privacy/retention behavior matches H11.
