# Phase 14 verification

**Close gate:** 2026-11-16, Windows 11, Python 3.12.16 (uv, frozen lockfile), Docker Desktop 4.99 (engine 29.9.3). Flags: `UCVE_ENV=test`, `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`. No live provider, carrier, deployment, publication or paid service was contacted.

## Spec verification command

| Command | Result |
|---|---|
| `python -m pytest tests/observability tests/compliance tests/jobs tests/scaling -q` | PASS — 109 passed |
| `python -m pytest tests voice_engine_plan/tests/phase_tests -q` | PASS — 1138 passed, 20 skipped |
| Disposable PostgreSQL `pytest tests/db` (migrations 001–036 from empty) | PASS — 54 passed, 1 skipped; teardown 0 containers/volumes/networks |
| `bash scripts/ops/run_privacy_proof.sh` (PostgreSQL + Adobe S3Mock) | PASS — hold, retention, erasure, append-only trail, storage-failure dead letter |
| `bash scripts/ops/drill_backup_restore.sh` | PASS — 55 tables, 35 migrations (checksums), 48 policies, all row counts identical; 0 pending after restore |
| `promtool check rules infra/observability/prometheus-alerts.yml` (prom/prometheus v2.54.1) | PASS — 12 rules |
| Local OpenTelemetry Collector (`docker-compose.observability.yml`) with the control plane exporting | PASS — 15 spans (`GET /health`, `GET /metrics`, `GET /v1/agents/{agent_id}`) and `ucve_http_*`, `ucve_event_loop_lag_ms` metrics received |
| Jobs container (`worker-jobs.Dockerfile`) against migrated disposable PostgreSQL | PASS — ready 200 in 3 s; 4 jobs scheduled, 2 disabled with reasons; SIGTERM exit 0 in 1 s; restart re-ready, slot not re-run |
| `python -m tests.scaling.drain_drill` | PASS — readiness 503 `draining`; new session refused 1013; live session completed; exit 0 after 7.8 s |
| `python -m tests.scaling.load_harness` (profiles dev/standard/high_density at and over capacity) | See table; reports in gitignored `hamza_local/phase14-load/` |
| `ruff check` / `ruff format` on Phase 14 files; `mypy` on new modules | PASS (pre-existing findings in untouched lines of edited legacy files left as they were) |
| `verify_plan_integrity.py` | PASS — 36 phases |
| Diff scans `b087147..HEAD`: `.github/`, deploy config, secret signatures, `git diff --check` | Clean |

## Load results (one machine, 12 logical CPUs, mock providers, real-speech clip)

| Profile × sessions | Admitted | Replies | Reply p50 / p95 | Worker RSS peak | CPU (1 core = 100%) | Loop lag p99 |
|---|---:|---:|---:|---:|---:|---:|
| dev × 5 | 5 | 15/15 | 868 / 890 ms | 121 MB | 15% | 23 ms |
| dev × 6 | 5 (+1 refused at mint) | 15/15 | 874 / 906 ms | 121 MB | 16% | 24 ms |
| standard × 25 | 25 | 75/75 | 1358 / 1409 ms | 131 MB | 58% | 424 ms* |
| standard × 26 | 25 (+1 refused) | 75/75 | 1329 / 1392 ms | 132 MB | 61% | 348 ms* |
| high_density × 40 | 40 | 120/120 | 1571 / 1864 ms | 140 MB | 99% | 462 ms* |

\* p99 over ~70 half-second samples is effectively the maximum; the slow-callback probe found a single ~185 ms stall while 25 sessions started at once. Steady-state p50 lag stayed ~0.6 ms. Reply time is measured by the client from the end of each spoken clip to the first returned audio byte and includes VAD end-of-speech detection; it is not the production latency metric.

ONNX A/B (2 sessions, 20 s, same speech): before the fix 460.6% of one core, loop lag p99 39 ms; after 6.1%, 24 ms.

## Failure-first notes (recorded honestly)

- Telemetry, readiness and alert tests were written alongside the implementations in the same step; earlier modules existed, so the new tests would have failed against them (no labels, no buckets, no `/health/ready`, no alert store), but those RED runs were not executed separately.
- Defects found by running things: OTLP export ignored `OTEL_EXPORTER_ENABLED` (4-second shutdown stalls); the harness's own unread stderr pipe blocked the worker (harness bug); a missing provider credential crashed the WebSocket; ONNX thread spinning; fleet admission cap; closing a draining WebSocket before accept surfaced as HTTP 403; tenant erasure tried to delete the immutable audit log; the quota runbook dropped the real 80% threshold; a tracker update was committed before the governance test was re-run (fixed in `03b34aa`).

## Not verified

Real AWS services (S3, RDS, ElastiCache, KMS), managed snapshots/PITR, production load on target hosts, live providers and carriers, Redis restart and network-failure drills (Phase 15), alert delivery to a real receiver (signature verified against a mock transport), Kubernetes/ECS probe wiring.
