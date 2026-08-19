# Telephony Integrator Guide

Inbound PSTN integration (Phases 18–19). Outbound campaigns are **[LATER]**.

## Inbound flow

```
PSTN → SIP trunk → telephony-gateway → worker-raw pipeline (same as native WS)
```

1. **Provision DID** on primary trunk (Telnyx DirectSIP or secondary adapter).
2. **Configure webhook URL** on carrier → `POST /v1/telephony/inbound` on control plane.
3. **Verify signature** — HMAC validation on webhook (habiba pattern, Phase 18).
4. **Normalize payload** — Phase 19 trunk adapter produces canonical `InboundCallEvent`.

## Required fields

| Field | Description |
|---|---|
| `caller_id` | E.164 calling party number — required; missing returns `CALLER_ID_MISSING` |
| `called_did` | Tenant-routed destination |
| `trunk_id` | Primary or failover trunk identifier |

## Media

- μ-law ↔ PCM16 transcoding in telephony-gateway (Phase 18).
- Sovereign path: no LiveKit required for call to connect.

## Outbound

**[LATER]** — outbound dialer and campaign APIs not in v1. Do not depend on outbound for production integrations.

## Failover

See [../runbooks/RUNBOOK_TRUNK_FAILOVER.md](../runbooks/RUNBOOK_TRUNK_FAILOVER.md) for dual-trunk promotion (Phase 19).

## Related

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — telephony error codes
- [INTEGRATION_PATTERNS.md](INTEGRATION_PATTERNS.md)
