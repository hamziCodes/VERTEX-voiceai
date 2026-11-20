# Phase 08C/08D Verification — Session Security and Auth Hardening

**Date:** 2026-10-22

**Branch:** `wavia-fixv1`

**Implementation commit:** `f2f861e27decf80b9c5e58bd51eb819e8eb28ab7`

**State:** verified; implementation committed and final evidence recorded here

## Implemented boundary

- API-key and signed mint requests are bound to the authenticated tenant and a
  tenant-owned published agent configuration.
- Nonces are consumed atomically with Redis `SET NX EX`; the locked in-memory
  implementation is limited to development/test. Protected environments fail
  closed when the replay store is unavailable.
- Session JWTs require issuer, audience, JTI, subject/session, tenant, agent,
  action, token type, issued-at, and expiry. Session access tokens expire in at
  most five minutes.
- A JTI admits one WebSocket connection. Refresh is single-use, revokes the old
  JTI for later admission, validates persisted session ownership, and issues a
  fresh JTI.
- Demo mint and shipped/default auth secrets are rejected in staging and
  production. Auth endpoints enforce bounded inputs, an 8 KiB request limit,
  direct-peer rate limiting, and sanitized failures.

## Test-driven evidence

The first contract-test collection failed because the new replay-store error
type did not exist. Implementation proceeded only after that expected red
state. All final commands forced offline behavior with `UCVE_ENV=test`, mock
providers enabled, live providers disabled, and live database tests disabled.

```text
pytest tests/auth tests/hardening/test_h1_auth_crypto.py \
  tests/hardening/test_h2_http_ws.py \
  voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py -q
56 passed, 3 warnings

pytest tests/auth tests/e2e/test_published_agent_runtime.py \
  tests/e2e/test_system_endpoints_e2e.py \
  tests/integration/test_realtime_protocol.py \
  voice_engine_plan/tests/phase_tests/test_phase_17_integration.py -q
40 passed, 1 warning

pytest -q --basetemp=hamza_local/pytest-phase8-full-final
659 passed, 1 skipped, 3 warnings

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.

python -m compileall -q core control_plane worker_raw tests
exit 0

ruff check <new Phase 08C/08D files>
All checks passed

ruff check --select F,UP,N <modified Phase 08C/08D paths>
All checks passed

git diff --check
exit 0

forbidden-scope check
passed

credential-pattern filename scan
passed
```

The warnings are the existing Starlette TestClient deprecation warning and two
short test-only JWT key warnings. Three pre-existing blind `Exception`
assertions remain in unrelated portions of two modified legacy test files; the
Phase 08 additions use typed exceptions and pass the targeted lint profile.

## Covered attacks and failure modes

- cross-tenant quick and signed mint with a valid API key;
- concurrent nonce replay, including 20 contenders with one winner;
- missing Redis/replay state in staging;
- missing claims and wrong JWT issuer, audience, action, or token type;
- reused WebSocket admission JTI and reused refresh JTI;
- refresh against the wrong persisted tenant, session, or agent;
- staging/production demo mode and default signing secrets;
- oversized auth requests and forwarded-header limiter spoofing;
- parser and internal failures reaching HTTP or WebSocket clients.

## Deliberate operational boundary

No live provider, IdP, database, Redis service, telephony call, or paid request
was used. Final deployment QA must wire durable API-key storage and Redis, then
exercise the same cases in the deployment environment without reusing test
secrets.

## Next exact action

Phase 08 is complete on `wavia-fixv1`. Do not push without a separate user
instruction. Start Phase 09 only when Hamzi explicitly requests it.
