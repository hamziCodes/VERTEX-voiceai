# Runbook: worker capacity and memory

## Capacity model

- `max_sessions_per_worker` (runtime profile `UCVE_RUNTIME_PROFILE`: dev 5, standard 25, high_density 40) is a **per-process** cap. A full worker reports `session_capacity` failing on `/health/ready` and refuses extra WebSocket sessions with close code 1013, so load balancers and clients go elsewhere.
- The shared admission cap across the fleet is `UCVE_CLUSTER_MAX_SESSIONS`, or `max_sessions_per_worker × UCVE_WORKER_REPLICAS`. Keep it in step with the real replica count; when the fleet is full, mint returns 503 and raises `CAPACITY_EXHAUSTED`.
- An unknown `UCVE_RUNTIME_PROFILE` fails readiness, and in staging/production the process refuses to start.

## Signals

`ucve_active_sessions{service="worker-raw"}` vs `ucve_worker_session_capacity`, `WaviaWorkerAtCapacity`, `WaviaEventLoopLagHigh` (`ucve_event_loop_lag_ms`), container memory/CPU from the orchestrator.

## Measured (Phase 14, offline load harness, one Windows machine, mock providers)

| Sessions | Replies | Reply p50 | Worker RSS peak | CPU (one core = 100%) | Loop lag p99 |
|---:|---:|---:|---:|---:|---:|
| 5 (dev) | 15/15 | 868 ms | 121 MB | 15% | 23 ms |
| 25 (standard) | 75/75 | 1358 ms | 131 MB | 58% | 424 ms (session start burst) |
| 40 (high_density) | 120/120 | 1571 ms | 140 MB | 99% | 462 ms |

Memory is not the constraint (~118 MB base, well under 0.5 MB per mock session); the single event loop is. Before Phase 14 the shared Silero ONNX session spun every core (~4.6 cores for two sessions); it is now pinned to one non-spinning thread — if CPU per session regresses, check `OMP_NUM_THREADS=1` and that fix first. Re-run on the target hosts with real providers:

```bash
python -m tests.scaling.load_harness --sessions 25 --seconds 60 --profile standard --out hamza_local/phase14-load/standard-25.json
```

## Immediate actions

1. Prefer adding worker replicas over raising the per-worker cap; update `UCVE_WORKER_REPLICAS`.
2. If a worker is OOM-killed, check the profile matches the container's memory and that nothing else shares the host.

## Escalation

SEV-2 if more than 25% of workers restart within 15 minutes.
