# Runbook: Trunk Readiness and New-Call Failover

## Fail-closed rules

A trunk is unavailable when health is unknown, disabled, missing its credential
reference or connection ID, or uses an adapter that is not implemented. Only an
explicitly healthy supported trunk can receive a new call.

Failover is evaluated for a new call only. Never move an established call to a
different carrier transparently. Finalize that call with its real failure reason.

## Symptoms

- `outbound_setup_unavailable` or `outbound_setup_not_ready`
- `outbound_provider_unavailable`
- `carrier_unavailable` or `carrier_result_ambiguous`
- no eligible primary trunk for a new call

## Checks

1. Confirm the tenant's agent is published and owns an active Telnyx DID.
2. Confirm the enabled trunk has a vault credential reference and connection ID.
3. Confirm trunk health is explicitly healthy; unknown is not healthy.
4. Confirm `UCVE_TELEPHONY_MEDIA_PUBLIC_URL` is the deployed exact `wss://` URL.
5. Confirm the tenant outbound policy is enabled and includes only the intended
   destination, time window, rate, concurrency, duration, and spend limits.
6. Inspect the durable outbound request by idempotency key. Do not redial an
   `ambiguous` request; reconcile it with carrier records first.

## Verification

Run the offline Phase 12E tests with live provider flags disabled. Live
certification is a separate approval gate and must use one approved destination.

## Escalation

Stop new calls on any destination mismatch, duplicate carrier charge, signature
failure, privacy leak, unexplained retry, or ambiguous carrier result that cannot
be reconciled.
