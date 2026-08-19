# Troubleshooting

Maps Phase 25 `UCVEErrorCode` values to integrator actions. Client messages are generic; use `correlation_id` from response headers or WS close metadata for support lookup.

| Code | Integrator action |
|---|---|
| `AUTH_INVALID` | Verify tenant API key and HMAC signing secret on mint proxy |
| `AUTH_EXPIRED` | Re-mint session token; check clock skew |
| `QUOTA_EXCEEDED` | Upgrade plan or wait for quota reset (Phase 14) |
| `PROVIDER_TIMEOUT` | Retry call; check provider status page; failover may apply |
| `PROVIDER_UNAVAILABLE` | Confirm ≥2 routes configured (Phase 06); open provider outage runbook |
| `FSM_INVALID_TRANSITION` | Client sent event out of order; reconnect with fresh mint |
| `BARGE_IN_FAILED` | Expected during TTS overlap; retry utterance |
| `HIPAA_BAA_REQUIRED` | Complete BAA gate before HIPAA tier (Phase 10) |
| `DATA_CLASSIFICATION_BLOCKED` | Field or content blocked by tier; adjust extraction schema |
| `WEBHOOK_SIGNATURE_INVALID` | Fix telephony webhook signing secret (Phase 18) |
| `TRUNK_UNAVAILABLE` | Check SIP trunk health; see trunk failover runbook |
| `CALLER_ID_MISSING` | Supply E.164 `caller_id` on inbound webhook normalize path |
| `EXTRACTION_FAILED` | Review post-call schema; check DLQ for job detail |
| `DISPATCH_FAILED` | Verify CRM webhook URL and HMAC secret; inspect DLQ |
| `REVIEW_REQUIRED` | Human review queue — check admin dashboard |
| `INTERNAL_ERROR` | Retry once; contact support with correlation_id only |

## Log lookup

1. Note `correlation_id` from `X-UCVE-Correlation-Id` (host-backend debug mode).
2. Search control-plane logs — never paste transcripts into tickets.
3. Cross-reference [../runbooks/README.md](../runbooks/README.md) for ops scenarios.

## WS disconnect checklist

- Sent `control.pong` on server ping (Phase 28 client duties)?
- Frame size within limit (Phase 01)?
- Mint token still valid?
