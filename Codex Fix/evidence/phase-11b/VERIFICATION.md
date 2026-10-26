# Phase 11B Verification Evidence

**Date:** 2026-10-26
**Branch:** `wavia-fixv1`
**Implementation commit:** `b510e8d`
**Result:** PASS

## Delivered behavior

- Finalizing a call creates one durable PostgreSQL outbox job in the same transaction.
- Workers claim jobs with leases, reclaim expired leases, apply bounded exponential retry, and terminate exhausted or non-retryable work in a dead-letter state.
- Extraction and summaries require explicit providers, strict JSON envelopes, known schema fields, declared primitive types, and transcript-backed evidence references. Missing values remain null with zero confidence.
- Intelligence results and any required review request commit atomically. Sensitive, uncertain, invalid, or configured external-action results cannot bypass review.
- Review decisions require tenant-bound `extraction:write` authority and are immutable and idempotent.
- HIPAA processing without the required BAA acknowledgement fails as a terminal safe compliance block.
- Phase 11B does not dispatch webhooks. Delivery remains blocked for Phase 11C.

## Automated verification

### Focused and compatibility tests

```powershell
py -3.12 -m pytest voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py tests/post_call tests/db/test_phase11_post_call_migration.py tests/db/test_phase11b_migration.py -q -p no:cacheprovider --tb=short
```

Result: **44 passed**.

The Phase 21 compatibility contracts now use deterministic provider fixtures and assert that webhook dispatch remains blocked until Phase 11C.

### Disposable PostgreSQL restart, RLS, and review test

Fresh local `pgvector/pgvector:pg16` and `redis:7-alpine` containers used generated credentials, temporary storage, and loopback-only ports. No shared database, provider, webhook, or call was used.

```powershell
py -3.12 -m pytest tests/db/test_phase11a_live_integration.py tests/db/test_phase11b_live_integration.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11b-disposable --tb=short
```

Result: **2 passed**. The test applies all migrations, closes and reopens the database pool, drains older queued work in deterministic order, persists result and review state, approves through authenticated tenant scope, verifies cross-tenant RLS isolation, and reruns migrations idempotently. Containers and volumes were removed afterward.

### Full forced-offline suite

```powershell
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11b-final --tb=short
```

Result: **828 passed, 9 skipped, 2 warnings** in 12.96 seconds. Both warnings are the existing intentionally short HMAC keys in `tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and changed-file lint: **passed**.
- Strict mypy with imported-module diagnostics suppressed: **14 Phase 11B source files passed**.
- Python compilation: **passed** for the changed runtime and test scope.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- `git diff --check`: **passed**.
- Staged scope: **24 intended files; zero `.env`, raw-key, legacy, or workflow paths**.
- Credential-literal scan: **zero hits** after replacing a long test-only HMAC fixture with an explicit short test value.

## Defect found during verification

The first combined disposable run exposed a test-order assumption: Phase 11A left an older queued job, so the global worker correctly processed that job first. The Phase 11B test now drains a bounded number of queued jobs until its target reaches `succeeded`; production FIFO behavior was preserved.

## Boundaries

- No live providers, phone calls, webhooks, cloud storage, paid traffic, or shared migrations were used.
- Provider interfaces and durable processing are implemented; production provider selection/wiring remains part of deployment configuration.
- Webhook target persistence, credential-reference resolution, SSRF controls, delivery attempts, and replay-safe dispatch are Phase 11C.
- Recording object storage, recursive privacy redaction, retention, legal hold, and erasure close in Phase 11D.

## Next exact action

Begin Phase 11C with failing tests for credential-reference-only webhook targets, reviewed HTTPS destination policy, canonical HMAC bytes, explicit deadlines, stored safe attempts, retry classification, and one logical delivery per `(tenant, target, call, event)` idempotency key.
