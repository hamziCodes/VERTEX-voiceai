# Phase 11C Verification Evidence

**Date:** 2026-10-26
**Branch:** `wavia-fixv1`
**Implementation commit:** `b64a8fe`
**Result:** PASS

## Delivered behavior

- Webhook targets store a tenant credential reference, never a raw signing key.
- Target activation requires tenant-authorized review plus an approved DNS address set.
- Delivery revalidates HTTPS, URL shape, port, public address, and the reviewed DNS set before every attempt. Redirects are never followed.
- The encrypted server-side vault adapter resolves only tenant BYOK `hmac_secret` credentials for the referenced target.
- The repository builds the outbound payload from the immutable approved intelligence result; callers cannot substitute arbitrary payload content.
- Canonical JSON bytes receive an HMAC-SHA256 signature and a stable logical idempotency key.
- PostgreSQL stores target, delivery, retry, lease, terminal state, and safe per-attempt evidence under tenant RLS.
- One worker claim performs one HTTP attempt. Retry scheduling is durable and bounded, so process restarts do not reset delivery state.
- HTTP connect/read/total timeouts and request-size limits are explicit. Responses are streamed for status only; response bodies are never read or stored.
- Missing credentials, unsafe endpoints, redirects, invalid/oversized payloads, permanent 4xx responses, timeouts, network failures, throttling, and 5xx responses receive typed safe outcomes.

## Automated verification

### Focused and compatibility tests

```powershell
py -3.12 -m pytest tests/post_call/test_webhook_policy.py tests/post_call/test_webhook_delivery.py tests/db/test_phase11c_migration.py voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py tests/hardening/test_remediation_r1_r7.py -q -p no:cacheprovider --tb=short
```

Result: **34 passed**.

Coverage includes raw-secret rejection, target approval evidence, unsafe URL and private-address rejection, DNS-change detection, review gating, immutable result payload construction, logical duplicate suppression, canonical HMAC bytes, stable idempotency headers, retry then success, terminal redirect handling, missing credential behavior, total timeout, request-size cap, vault resolution arguments, and response-body exclusion.

### Disposable PostgreSQL restart, delivery, and RLS tests

A fresh local `pgvector/pgvector:pg16` database and `redis:7-alpine` instance used generated credentials, temporary storage, and loopback-only ports. HTTP delivery used `httpx.MockTransport`; no network destination was contacted.

```powershell
py -3.12 -m pytest tests/db/test_phase11a_live_integration.py tests/db/test_phase11b_live_integration.py tests/db/test_phase11c_live_integration.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11c-disposable --tb=short
```

Result: **3 passed**. The sequence applies every migration, persists and reopens webhook work, delivers once, records one safe attempt, suppresses a duplicate logical delivery, verifies cross-tenant RLS, and reruns migrations idempotently. The final Phase 11C-only run also passed after streamed-response hardening. Containers and volumes were removed.

### Full forced-offline suite

```powershell
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11c-final --tb=short
```

Result: **844 passed, 10 skipped, 2 warnings** in 10.68 seconds. Both warnings are the existing intentionally short HMAC keys in `tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and Phase 11C changed-file lint: **passed**.
- Strict mypy with imported-module diagnostics suppressed: **7 webhook source files passed**.
- Python compilation: **passed** for Phase 11C runtime and tests.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- `git diff --check`: **passed**.
- Staged scope: **13 intended files; zero `.env`, raw-key, legacy-codebase, or workflow paths**.
- Credential-literal scan: **zero production or high-risk test hits**.

## Migration decision and boundary

Migration 012 already defines an unused legacy `webhook_targets` table with raw `secret` storage. Reusing it would require deleting or transforming possible existing credentials. Phase 11C therefore creates `post_call_webhook_targets`, and all new runtime code uses only this credential-reference table. No shared migration or destructive legacy-data change was performed.

Before production migration, Phase 11D must inventory any legacy rows, move each secret into the encrypted vault with an explicit credential reference, verify the new target, and only then remove the legacy table/column under the destructive-migration approval gate. Until that migration runs, existing legacy rows are not dispatchable through Phase 11C.

## Boundaries

- No live webhook, provider, call, cloud service, paid traffic, or shared database was used.
- A receiving system must honor `X-Idempotency-Key` to suppress a replay after the remote accepted a request but the worker crashed before recording success.
- Public DNS is rechecked against the approved set before each request. Network-level egress controls remain recommended in production to close resolver-to-connect races outside application control.
- Audit event integration and retention/erasure of targets, deliveries, and attempts close in Phase 11D.

## Next exact action

Begin Phase 11D with failing tests for recursive structured-log redaction, bounded recording object storage, legal hold, retention claims, restartable tenant erasure, webhook-data cleanup, and the gated migration of any legacy raw-secret webhook rows.
