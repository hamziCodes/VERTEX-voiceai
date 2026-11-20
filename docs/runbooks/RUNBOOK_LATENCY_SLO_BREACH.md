# Runbook: latency SLO breach

The latency metric is **end of user speech to first audible assistant sample**. Targets (`core/latency/slo_policy.py`): p50 450 ms, p95 850 ms. Breaches are warn-only: sessions are never killed automatically.

## Signals

- Prometheus `WaviaTurnLatencyP95AboveSLO` (p95 > 850 ms for 10 min) and `WaviaTurnLatencyP50AboveTarget` over `ucve_turn_latency_ms{measurement_quality="server_ack_upper_bound"}` (turns with a client playback acknowledgement).
- Stage breakdown: `ucve_turn_stage_ms{stage}` — `vad_tail`, `stt_after_vad`, `rag`, `llm_ttft`, `tts_ttfb`, `server_send`.
- Per-turn traces (when OTLP export is on) and `metric.latency` events sent to SDK clients.

## Immediate actions

1. Find the dominant stage:
   ```promql
   histogram_quantile(0.95, sum by (le, stage) (rate(ucve_turn_stage_ms_bucket[10m])))
   ```
2. Check worker health before blaming providers: `WaviaEventLoopLagHigh`, `ucve_active_sessions` against `ucve_worker_session_capacity`.
3. Provider stages high → `rate(ucve_provider_failover_total[5m])`; repeated failover adds latency. See RUNBOOK_PROVIDER_OUTAGE.

## Mitigation

- Worker saturation: add worker replicas (and raise `UCVE_WORKER_REPLICAS` / `UCVE_CLUSTER_MAX_SESSIONS` to match), or move to a lower-density profile. Phase 14 load tests on one machine: replies took ~0.83 s p50 at 5 sessions and ~1.36 s at 25 with mock providers — treat 25 sessions per worker (standard profile) as capacity, not as an SLO-safe density, until measured on the target hosts.
- Provider stage: change the agent's route order in Studio (advanced mode) if quality allows.

## Escalation

SEV-3 when p95 stays above target for 30 min; SEV-2 when p99 causes user-visible timeouts.
