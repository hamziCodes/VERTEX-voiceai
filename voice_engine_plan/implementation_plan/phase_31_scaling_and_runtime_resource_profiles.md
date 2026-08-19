# Phase 31: Scaling and Runtime Resource Profiles

## 1. Executive Summary & Core Logic

Define horizontal scaling rules, per-session resource budgets, and runtime profiles so operators know when to add workers vs tune pools — closing habiba's LiveKit deployment cap lesson (`legacy_codebases/habiba-sdk-agent/docs/11-ARCHITECTURE.md` — 4 agent deployments limit) and in-process rate limiter gap (AUDIT_04 §5). Extends Phase 17 single-worker estimates into production sizing tables keyed by concurrent session targets.

Depends on Phase 17 pipeline resource notes, Phase 02 buffer limits, Phase 06 provider pool config, Phase 14 quota admission, Phase 30 compose/K8s topology, Phase 07 metrics for autoscale signals.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Scale workers on **active session count** | File 9 §4.2 — CPU alone misleading with Silero pool |
| Redis-backed admission (Phase 14) | Fixes habiba in-process limiter (File 9 §5 #12) |
| Silero pool size = f(concurrent sessions) | File 1 §3.2 — bounded per-process inference |
| Named runtime profiles: `dev`, `standard`, `high_density` | Operator-selectable without code forks |
| HPA metric: `ucve_active_sessions` | Phase 07 custom metric |

**Reference docs:** blueprint File 01 §3.2–§3.3; File 09 §4.2; habiba `docker/worker.Dockerfile` env tuning (AUDIT_04 §5).

## 3. What / How / Why

- **What:**
  - **`RuntimeProfile` enum:** `{dev, standard, high_density}` — JSON config in `infra/scaling/profiles/`
  - **Per-profile tables:** `{max_sessions_per_worker, silero_pool_size, asyncio_worker_tasks, redis_memory_mb, postgres_conn_pool}`
    - **dev:** 5 sessions/worker, pool 2
    - **standard:** 25 sessions/worker, pool 4 (default prod)
    - **high_density:** 40 sessions/worker, pool 6 — requires Phase 02 buffer tuning review
  - **`SessionAdmissionController`:** integrates Phase 14 quota + profile cap — reject mint when worker at profile limit (503 + `QUOTA_EXCEEDED` or capacity code)
  - **`AutoscalerHints`:** document K8s HPA on `ucve_active_sessions` + CPU floor; scale-to-zero **not supported** (cold Silero pool ~2 s)
  - **Memory budget doc:** ~150 MB base + ~50 MB Silero pool + ~3 MB/session (Phase 17) — table in `docs/scaling/RESOURCE_TABLE.md`
  - **Provider connection pooling:** STT/LLM/TTS client reuse per worker — max concurrent provider streams per profile
  - **telephony-gateway scaling:** separate from worker-raw when DirectSIP media load high — 1 gateway pod per 50 concurrent PSTN legs guideline
- **How:** Worker reads `UCVE_RUNTIME_PROFILE` env at boot → loads profile YAML → configures Silero pool + admission limit. Control-plane mint checks cluster-wide active sessions via Redis counter (Phase 14). Document upgrade path: dev → standard → high_density with load test evidence (Phase 33).
- **Why this approach:** Habiba LiveKit scale capped tenants at 4 (architecture doc). UCVE must scale on session count with sovereign workers. **CPU-only autoscale rejected** — Silero-bound workloads need session metric. Alternative: unlimited sessions per worker — OOM under Silero load.

## Deliverables

- `infra/scaling/profiles/dev.yaml`
- `infra/scaling/profiles/standard.yaml`
- `infra/scaling/profiles/high_density.yaml`
- `core/runtime/profile_loader.py` — `RuntimeProfile` loader
- `core/runtime/admission.py` — `SessionAdmissionController`
- `docs/scaling/RESOURCE_TABLE.md`
- `docs/scaling/AUTOSCALING.md` — HPA hints + metrics
- `docs/scaling/LIVEKIT_SCALE_LESSON.md` — habiba citation + UCVE contrast

## 4. Compute & Resource Profile (if applicable)

| Profile | Sessions/worker | Worker RAM | Worker vCPU |
|---|---|---|---|
| dev | 5 | 4 GB | 2 |
| standard | 25 | 8 GB | 4 |
| high_density | 40 | 16 GB | 8 |

50 concurrent standard-tier sessions ≈ 2× standard workers + 1 control-plane (HA optional).

## 5. Compliance Notes (if applicable)

Admission rejections must not leak tenant queue positions or other tenant IDs in error messages (Phase 25 generic errors). Profile configs contain no secrets. High-density mode requires HIPAA review if PHI-heavy — document increased blast radius on shared worker.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Primary scale metric:** **active session count** (`ucve_active_sessions`) — CPU as secondary floor, not primary.
2. **Default production profile:** **`standard`** (25 sessions/worker) — high_density requires explicit opt-in + Phase 33 load evidence.
3. **Scale-to-zero:** **not supported** — Silero pool warm-up unacceptable for inbound PSTN answer SLA.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_31_scaling_profiles.py`
- **Asserts:** three profile YAML files load; profile_loader sets silero_pool_size; admission rejects when at cap; RESOURCE_TABLE documents Phase 17 memory model; AUTOSCALING references ucve_active_sessions; dev profile lower cap than standard.
- **Pass threshold:** 100% profile loader + admission unit tests.
- **Latency target:** admission check < 5 ms p99 (Redis counter).
