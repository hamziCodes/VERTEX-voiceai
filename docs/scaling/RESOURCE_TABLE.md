# Scaling Resource Table

Resource budgets and concurrency boundaries across runtime profiles (Phase 31).

## Memory Model (Phase 17 Sizing)

A worker-raw process base memory footprint consists of:
- **Base runtime overhead:** ~150 MB (FastAPI, Python runtime, PyTorch core imports)
- **Silero VAD Pool:** ~50 MB per pool instance (ONNX / Torch JIT model in memory)
- **Per-active session overhead:** ~3 MB / session (frame ring buffers, sentence bridge, FSM state)

```
Total Memory ≈ 150 MB + (silero_pool_size × 50 MB) + (active_sessions × 3 MB)
```

## Runtime Profile Specifications

| Metric | `dev` | `standard` (Default Prod) | `high_density` |
|---|---|---|---|
| **Max Concurrent Sessions** | 5 | 25 | 40 |
| **Silero VAD Pool Size** | 2 | 4 | 6 |
| **Asyncio Worker Tasks** | 4 | 8 | 12 |
| **Worker RAM Allocation** | 4 GB | 8 GB | 16 GB |
| **Worker vCPU Allocation** | 2 vCPU | 4 vCPU | 8 vCPU |
| **Redis Memory Limit** | 512 MB | 1024 MB | 2048 MB |
| **Postgres Connection Pool** | 5 | 20 | 30 |
| **Max Provider Streams** | 10 | 50 | 80 |

## Cluster Dimensioning Guidelines

For 100 concurrent calls in `standard` profile:
- 4× `worker-raw` instances (25 sessions each)
- 2× `control-plane` instances (stateless load-balanced)
- 1× `telephony-gateway` pair (2 instances for 100 PSTN legs)
- Managed or HA PostgreSQL + Redis cluster
