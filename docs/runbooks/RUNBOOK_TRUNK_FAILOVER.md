# Runbook: Trunk Failover

Phase 19 dual-trunk readiness.

## Symptoms

- `TRUNK_UNAVAILABLE` on inbound webhooks
- SIP OPTIONS failures on primary trunk
- Calls failing before worker pipeline

## Immediate actions

1. Check telephony-gateway health and trunk probe status.
2. Confirm `caller_id` present on last failed webhook (required field).
3. If dual trunk configured: promote secondary in control-plane trunk registry.
4. Update carrier webhook URL if primary POP unreachable.

## Single-trunk tenants

- No automatic failover — document `[LATER]` outbound + hot standby
- Mitigate: carrier status page, manual reroute DID

## Verification

- Place test inbound call with sanitized fixture (Phase 33 E2E)
- Confirm normalization via Phase 19 adapter

## Escalation

SEV-2 inbound PSTN down > 10 min for any production tenant.
