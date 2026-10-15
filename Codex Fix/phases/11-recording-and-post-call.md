# Phase 11 — Recording, Transcripts, and Post-Call Intelligence

**Status:** NOT STARTED

**Goal:** Persist honest call records and execute extraction, verification, human review, summaries, webhooks, retention, and erasure through durable jobs.

**Depends on:** Phase 09. Integrates Phase 10 tool/data schemas where relevant.

**Audit coverage:** F06, F11, I08 extraction, I09, I10, I13 post-call.

## Human gate before implementation

Resolve H11 before enabling recording or retention defaults. Until then, use no-recording by default and generated test transcripts.

## Files and interfaces

- Modify: session lifecycle to capture accurate start/end/transport/provider/usage and recording availability.
- Implement: object storage adapter, durable post-call queue/worker/retry/DLQ, extraction and webhook repositories.
- Modify: redaction/logging/audit/retention/erasure services.
- Test: persistence/restart, actual/no recording, extraction evidence, review gate, webhook replay, retention and erasure.

## Tasks

- [ ] Create the call record at admission with real start time; finalize idempotently with end/disposition/metrics.
- [ ] Never manufacture recording URI/dual-channel metadata. Store `not_requested`, `recording`, `available`, or `failed` state with evidence.
- [ ] Persist transcript turns incrementally so provider/post-call failures do not erase the conversation.
- [ ] Replace process-list enqueue with durable queue/outbox, retries, DLQ, leases and idempotency.
- [ ] Replace fabricated extraction/summary/sentiment with schema-valid model/provider output plus source evidence/confidence; missing stays null.
- [ ] Route configured/high-risk actions through human review before webhook/CRM dispatch.
- [ ] Implement real HTTP webhook delivery with HMAC, timeout/backoff/idempotency and stored attempt/result.
- [ ] Apply recursive privacy redaction; remove transcript previews/vendor response bodies from default logs.
- [ ] Implement object deletion, legal hold, retention jobs and async-safe erasure across DB/storage/queues/audit. Failed partial erasure remains failed and retryable.
- [ ] Test restart, duplicate finalize/job/webhook, extraction invalid JSON, missing review, storage failure, legal hold, and complete tenant erasure.

## Verification

```powershell
python -m pytest tests/post_call tests/compliance tests/e2e/scenarios/test_post_call_e2e.py -q
```

Expected: durable exactly-once logical outcome under retries; accurate timestamps/recording state; no fabricated summaries; review blocks configured action; erasure reports complete only when all stores succeed.

## Human intervention

Hamzi approves retention/recording/review policy. A real webhook destination or cloud bucket is a separate live integration approval.

## Exit criteria

- Post-call work survives process restart.
- Dashboard/API can distinguish pending, succeeded, reviewed and failed outcomes.
- Privacy/retention behavior matches H11.
