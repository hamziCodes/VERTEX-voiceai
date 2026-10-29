# Phase 12E Verification Evidence

**Implementation commits:**

- `1cb234c` — fail-closed outbound trunk readiness
- `038cd64` — controlled, durable single-call outbound telephony

**Safety boundary:** all verification was forced offline. No Telnyx account,
credential value, carrier request, provider call, shared database migration,
deployment, or paid action was used. `RUN_LIVE_TELEPHONY=0` remained set.

## Implemented contract

- Added authenticated `POST /v1/telephony/calls` with tenant identity derived
  from the authenticated API key and the `telephony:write` permission.
- Accepts one published agent, one E.164 destination, purpose, consent reference,
  and idempotency key. There is no batch, campaign, or contact-list surface.
- Added durable tenant policy and request records with PostgreSQL RLS, an exact
  destination allowlist, calling window, concurrency/rate limits, daily spend
  cap, per-call reservation, maximum duration, and request fingerprint.
- Atomically resolves a tenant-owned published agent, active Telnyx DID, enabled
  trunk, tenant vault credential reference, and connection ID.
- Added a bounded Telnyx Dial client using one command ID. Connect/5xx retries
  reuse the same payload; read/write uncertainty becomes `ambiguous` and the
  same application idempotency key cannot blind-redial it.
- Added a separate `RUN_LIVE_TELEPHONY=1` boundary before secret resolution or
  network access. Missing secure media URL leaves the production service absent.
- Unknown health, missing configuration, and unimplemented carriers fail closed.
  Secondary selection applies only to a new call; no mid-call migration is
  claimed.
- Added outbound request/policy tables to tenant privacy erasure and aligned the
  executable endpoint, configuration, SDK, security, and runbook documentation.

## Failure-first proof

- New outbound tests initially failed at import because the policy provider and
  credential-resolving dialer did not exist.
- New durable-policy tests initially failed because the PostgreSQL outbound
  repository did not exist.
- The first full suite found six legacy assertions that treated unknown health,
  a missing connection ID, and an unimplemented Twilio adapter as usable. Those
  assertions were updated to the Phase 12E fail-closed contract; production code
  was not weakened to preserve unsafe behavior.

## Verification results

The repository's ignored local Python 3.14.2 environment was used because the
Windows `py -3.12` launcher is unavailable in this checkout.

- Phase 12E contract plus E2E: **81 passed**.
- Durable repository, auth matrix, and privacy regression: **31 passed**.
- Legacy security/telephony/developer-experience regression: **28 passed**.
- Full forced-offline repository suite: **929 passed, 13 skipped**, with six
  known warnings (short test HMAC keys and Starlette's 422 deprecation).
- Focused Ruff checks: passed.
- `compileall` for telephony, control plane, and DB repositories: passed.
- Voice-engine plan integrity: **36 phases, tests, and trackers verified**.
- `git diff --check`: passed.

## Deferred disposable PostgreSQL proof

`tests/db/test_phase12e_live_outbound.py` was added for migration application,
restart-safe idempotency, policy limits, RLS isolation, and migration re-entry.
It was not executed because Docker Desktop was not running (the local Docker
engine pipe was unavailable). This is the first required action in Phase 12F;
it does not require a carrier, credential, live call, or charge.

## Next exact action

Begin Phase 12F. Start Docker Desktop, run the disposable Phase 12 PostgreSQL
test including `test_phase12e_live_outbound.py`, tear it down with volumes, then
run the Phase 12 offline close gate. Keep live certification blocked until Hamzi
separately approves one destination, spend cap, time window, and live call.
