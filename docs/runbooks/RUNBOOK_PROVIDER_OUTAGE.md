# Runbook: Provider Outage

Phase 06 circuit breaker + failover router.

## Symptoms

- Spike in `PROVIDER_UNAVAILABLE` / `PROVIDER_TIMEOUT`
- Circuit breaker open metrics (Phase 07)
- Failover route accepting traffic

## Immediate actions

1. Identify vendor category: STT, LLM, or TTS from alert labels.
2. Confirm ≥2 routes configured — startup should fail with only one (File 9 #18).
3. Verify secondary route completing turns in staging logs.
4. If all routes down: enable mock/degraded mode **dev only** — not prod.

## Manual promotion

```text
1. Open provider registry admin
2. Set failed route weight=0
3. Promote secondary to primary
4. Document change in incident ticket
```

## Communication

- Tenant webhook: generic "degraded performance" — no vendor names in client WS errors (Phase 25).
- correlation_id for support.

## Recovery

- Wait for circuit half-open probe success
- Gradually restore primary weight
- Post-incident: review Phase 24 latency waterfall for regression

## Escalation

SEV-2 if single category fully down > 5 min; SEV-1 if all categories down.
