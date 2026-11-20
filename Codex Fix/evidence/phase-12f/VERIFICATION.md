# Phase 12F Offline Close-Gate Evidence

**Close-gate cleanup commit:** `df9c4d4` — telephony package lint cleanup.

**Safety boundary:** all commands were local and forced offline. No Telnyx
credential was resolved, no carrier/provider endpoint was contacted, no call was
placed, and no charge, deployment, publish, or shared migration occurred.
`RUN_LIVE_TELEPHONY=0` and `RUN_LIVE_PROVIDERS=0` remained set.

## Disposable PostgreSQL proof

The repository's `infra/docker/docker-compose.phase12-test.yml` started one
temporary pgvector/PostgreSQL container on loopback. The following isolated
tests passed:

- Phase 12B durable call identity, event/command idempotency, migration re-entry,
  and tenant RLS.
- Phase 12E outbound policy, durable request idempotency, concurrency limit,
  migration re-entry, and tenant RLS.

Result: **2 passed**. The container, network, and volumes were removed in the
command's `finally` block.

## Offline close gate

- `tests/telephony` plus the inbound telephony E2E: **62 passed**, with four
  known Starlette 422-deprecation warnings.
- Full forced-offline repository suite: **929 passed, 13 skipped**, with six
  known warnings (short test HMAC keys and Starlette's 422 deprecation).
- Exact Phase 12 Ruff scope (`telephony_gateway`, `worker_raw/telephony`, and
  `tests/telephony`): passed.
- Telephony package/worker `compileall`: passed.
- Voice-engine integrity: **36 phases, tests, and trackers verified**.
- `git diff --check`: passed.

The local ignored Python 3.14.2 environment was used because the Windows
`py -3.12` launcher is unavailable in this checkout.

## Exit assessment

Phase 12's offline exit criteria are satisfied:

- signed, replay-safe inbound admission is durable and tenant-bound;
- fake-carrier media proves bidirectional voice, interruption, cleanup, and
  once-only metering/post-call behavior;
- outbound is a single authenticated call with policy, idempotency, rate, spend,
  duration, consent, and destination controls;
- unknown/incomplete/unimplemented trunks fail closed;
- executable endpoint/configuration documentation matches the implemented path;
- campaigns and bulk dialing remain unavailable.

This evidence does **not** certify live carrier behavior. Production/live
readiness remains blocked until Phase 15 and requires Hamzi's separate approval
of one destination, spend cap, permitted window, deployment, and live call.

## Next exact action

Resolve H13 before Phase 13: confirm the self-serve onboarding fields, billing
boundary, and design process. Do not infer those product decisions.
