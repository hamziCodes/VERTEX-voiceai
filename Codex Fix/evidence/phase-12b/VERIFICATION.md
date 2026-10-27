# Phase 12B Verification Evidence

**Date:** 2026-10-27

**Branch:** `wavia-fixv1`

**Implementation commit:** `4d8bf04`

**Result:** PASS

## Delivered behavior

- Added append-only migration `028_telephony_runtime.sql` for durable calls,
  accepted carrier events, and reserved carrier commands.
- One Telnyx `call_control_id` now maps to one stable internal session UUID across
  retries, process restarts, and valid reordered events.
- Carrier event IDs are accepted once under PostgreSQL advisory locks and a
  primary-key constraint. A duplicate returns the existing safe acknowledgement
  without repeating lifecycle work.
- Lifecycle state advances only forward through `received`, `admitted`,
  `answered`, `media_active`, `ending`, and the terminal `ended`/`failed` states.
  Lower-state events that arrive late remain recorded without regressing the call.
- Inbound DID admission requires normalized E.164, an active durable Telnyx DID,
  matching tenant ownership, an active tenant, and the agent's current immutable
  published version. Unknown, inactive, unpublished, or identity-changing events
  fail closed.
- Carrier command reservation is separate from webhook receipt and enforces one
  durable `(tenant_id, idempotency_key)` record.
- The gateway constructs the PostgreSQL event sink only when durable database
  configuration is present; missing verification or persistence configuration
  remains unavailable/fail closed.
- Removed the legacy handler that fabricated call/session IDs, resolver demo DID
  mappings, exception swallowing, the mismatched `phone_number` query, and the
  fabricated default trunk.
- Canonical `ucve_app` RLS policies now cover DIDs, trunks, calls, events, and
  commands. Composite foreign keys enforce tenant ownership for calls and future
  DID writes.
- Tenant privacy erasure now deletes command/event/call rows before referenced
  agent and DID records.

## Failure-first evidence

The new lifecycle test first failed during collection because the durable
telephony repository did not exist. After implementation, the first disposable
PostgreSQL run found an incorrect test expectation: one tenant correctly saw
three accepted event rows rather than one. The assertion was corrected to use
per-table expected counts; no runtime behavior was weakened.

The first full-suite run found a Python test-module basename collision with the
existing post-call `test_call_lifecycle.py`. Adding the telephony test package
boundary resolved collection while retaining the checkpoint's required filename.

## Automated verification

### Focused and related offline regression

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:RUN_MOCK_PROVIDERS='1'
$env:UCVE_ENV='test'
py -3.12 -m pytest tests/telephony/test_call_lifecycle.py tests/telephony/test_telnyx_webhook_security.py tests/hardening/test_remediation_r1_r7.py voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py tests/compliance/test_phase11_erasure.py tests/compliance/test_phase11_privacy.py tests/db/test_phase11d_live_integration.py -q -p no:cacheprovider
```

Result: **64 passed, 1 skipped** in 2.89 seconds. The skip is the explicitly
gated live-database Phase 11D test.

### Disposable PostgreSQL proof

```powershell
$env:PHASE12_DB_PASSWORD=[guid]::NewGuid().ToString('N')
docker compose -f infra/docker/docker-compose.phase12-test.yml up -d --wait
$env:DATABASE_URL="postgresql://phase12:$($env:PHASE12_DB_PASSWORD)@127.0.0.1:55433/phase12"
$env:RUN_LIVE_DB_TESTS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest tests/db/test_phase12b_live_telephony.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12b-disposable-final
docker compose -f infra/docker/docker-compose.phase12-test.yml down --volumes
```

Result: **1 passed** in 0.77 seconds. The test proved migration replay safety,
restart-stable session identity, duplicate event rejection, reordered-event state
monotonicity, command idempotency, and tenant RLS across all five telephony table
families. The container, network, tmpfs data, and volume were removed afterward.

### Full forced-offline suite

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12b-full-final
```

Result: **888 passed, 12 skipped, 2 warnings** in 12.48 seconds. The warnings are
the existing intentionally short HMAC fixtures in
`tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and scoped lint: **passed**.
- Scoped mypy with imported-module noise skipped: **4 source files passed**.
- Python compilation: **passed**.
- `git diff --check`: **passed**.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- Windows `%SystemDrive%` test cache artifacts were moved intact into gitignored
  `hamza_local` quarantine directories; nothing was committed or deleted.

## Boundaries and next exact action

- No environment file, raw key file, shared database, Telnyx account, carrier
  endpoint, provider, destination number, deployment, paid traffic, or live call
  was accessed.
- Phase 12B establishes durable admission and identity. It does not answer a call,
  execute a carrier command, open carrier media, or claim audible telephony.
- Begin Phase 12C with failure-first fake-carrier tests for a call-bound media
  WebSocket, base64 G.711 mu-law ingress/egress, stateful resampling, exact 20 ms
  pacing, bounded queues, sequence/loss/reorder policy, and deterministic cleanup.
  Do not contact Telnyx.
