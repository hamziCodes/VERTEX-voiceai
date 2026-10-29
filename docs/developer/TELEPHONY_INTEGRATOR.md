# Telephony Integrator Guide

Wavia currently supports signed Telnyx inbound admission and one controlled
outbound call request. Bulk contact lists, campaigns, predictive dialing, and
automatic mid-call carrier migration are intentionally unavailable and remain
later work.

Inbound admission rejects a missing or invalid E.164 caller identity with the
stable `CALLER_ID_MISSING` contract.

## Executable endpoints

| Service | Method and path | Purpose |
|---|---|---|
| telephony-gateway | `POST /v1/telephony/webhooks/telnyx` | Exact-body, Ed25519-verified Telnyx event admission |
| control-plane | `POST /v1/telephony/calls` | Authenticated, tenant-scoped single outbound call request |

The outbound route requires an API key with `telephony:write`. Tenant identity
comes from authentication, never from the request body. The body contains one
published `agent_id`, one E.164 destination, purpose, consent reference, and
idempotency key.

## Required outbound setup

An operator must configure, per tenant:

- one active tenant-owned Telnyx DID assigned to the published agent;
- one enabled Telnyx trunk with a vault credential reference and connection ID;
- an enabled outbound policy containing an exact destination allowlist, calling
  timezone/window, concurrency/rate limits, daily spend cap, per-call spend
  reservation, and maximum call duration;
- `UCVE_TELEPHONY_MEDIA_PUBLIC_URL` as the exact public `wss://` media endpoint;
- a tenant BYOK Telnyx API credential in the Wavia secret vault.

`TELNYX_API_KEY` and `TELNYX_CONNECTION_ID` are legacy/platform configuration
names. The controlled outbound path resolves the tenant credential reference and
connection ID from durable tenant configuration.

## Safety gate

`RUN_LIVE_TELEPHONY=1` is required before credential resolution or any Telnyx
Dial request. Keep it `0` by default. Enabling it does not bypass the destination
allowlist, consent, time window, concurrency, rate, spend, or idempotency checks.

Carrier timeouts after submission are recorded as ambiguous and are not blindly
redialed. Reuse the same idempotency key to retrieve the existing request.

## Certification boundary

Offline tests use generated audio, fake providers, and a local fake carrier. A
real call is not part of normal verification. Live certification requires
Hamzi's separate approval, one approved allowlisted destination, an explicit
spend cap and time window, and a deployed authenticated media endpoint.

## Failover

Failover selection applies only before a new call. An established call is ended
and finalized honestly if its carrier path fails; Wavia does not claim transparent
mid-call carrier migration.

See [RUNBOOK_TRUNK_FAILOVER.md](../runbooks/RUNBOOK_TRUNK_FAILOVER.md).
