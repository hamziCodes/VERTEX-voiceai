# Runbook: Latency SLO Breach

Phase 24 warn-only SLO interpretation.

## Symptoms

- `LATENCY_SLO_BREACH` alert from LatencyBenchmarkHarness
- Elevated `LatencyWaterfall.total_e2e_ms` p95
- Tenant reports sluggish responses (not hard failures)

## Immediate actions

1. Pull waterfall breakdown: VAD, STT, LLM TTFT, TTS TTFB (Phase 24).
2. Identify dominant stage — do not restart workers blindly.
3. **Warn-only:** no automatic session kill; document breach duration.

## Common causes

| Stage | Check |
|---|---|
| STT | Provider latency or failover thrash |
| LLM | Model route overload |
| TTS | Chunker or transcoding delay |
| Silero | Pool saturation — see RUNBOOK_WORKER_OOM |

## Mitigation

- Shift traffic to faster route if quality acceptable
- Reduce concurrent sessions per worker (Phase 31 profile)
- Scale worker count on `ucve_active_sessions`

## Escalation

SEV-3 sustained p95 > 2× target for 30 min; SEV-2 if p99 causes user-visible timeouts.
