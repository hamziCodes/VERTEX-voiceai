# Phase 09C — Redis Admission Leases

**Status:** VERIFIED AND COMMITTED — `b439437`

## Implemented

- Added one atomic Redis Lua acquisition covering expired-lease cleanup,
  idempotent reacquisition, tenant concurrency, worker concurrency, session TTL,
  and both tenant/global indexes.
- Added heartbeat extension, idempotent release, and stale reconciliation.
- Added a locked, clock-controlled memory implementation for tests/local
  development. Protected environments require Redis and fail closed.
- Session mint acquires the tenant lease before persistence and releases it if
  session persistence or JWT issuance fails.
- Worker admission reacquires the same lease idempotently, refreshes it from the
  WebSocket keepalive loop, and releases it during owned teardown.
- Test mode ignores ambient Redis configuration unless a fake client is
  explicitly injected, preventing accidental network access during tests.

## Verification

```text
pytest tests/metering/test_admission_leases.py \
  tests/auth/test_session_security.py tests/e2e/test_session_cleanup.py \
  tests/e2e/test_published_agent_runtime.py \
  voice_engine_plan/tests/phase_tests/test_phase_31_scaling_profiles.py -q
39 passed, 1 warning
```

No Redis command reached an external service. The warning is the existing
Starlette TestClient deprecation warning.
