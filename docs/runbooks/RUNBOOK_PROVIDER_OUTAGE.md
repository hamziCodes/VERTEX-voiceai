# Runbook: provider outage

Each agent publishes a priority chain per category (STT, LLM, TTS). The failover router moves to the next route on errors, timeouts or an open circuit; a chain is exhausted when every route failed or was unavailable.

## Signals

- `ucve_provider_failover_total{category}` and Prometheus `WaviaProviderFailoverRateHigh` (> 0.2 failovers/s for 5 min).
- Durable alert `PROVIDER_CHAIN_EXHAUSTED` (critical, key `provider_chain_exhausted:<category>`, facts: category, failed_routes) — raised the moment a whole chain fails.
- Clients receive typed `degraded`/`error` events (no vendor names). A session whose tenant credential is missing ends with `PROVIDER_CREDENTIAL_MISSING` and close code 1011 — that is configuration, not an outage.
- Provider readiness on `/health/ready` is configuration-only (`providers` check); there is deliberately no live probe (it would cost money). `/admin/operations` shows provider health as **Not measured** for the same reason.

## Immediate actions

1. Identify the category from the alert facts.
2. Check the vendor's status page. Workers keep routing to the next healthy route automatically; do not restart workers.
3. If one vendor is down for long, change the route order in the agent (Studio advanced mode) and publish — new sessions pin the new plan; live sessions keep theirs.
4. Never switch production to mock providers.

## Recovery

Circuits half-open and probe on real traffic; failover rate returns to zero. Resolve the alert in `/admin/operations` (or `POST /v1/platform/alerts/{alert_id}/resolve`) once traffic is healthy.

## Escalation

SEV-2 if one category is exhausted for more than 5 minutes; SEV-1 if all categories are.
