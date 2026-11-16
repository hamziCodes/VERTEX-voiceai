# Phase 14 progress — operations, compliance and cleanup

**Branch:** `wavia-fixv1` (pushed)
**Spec:** `Codex Fix/phases/14-operations-compliance-cleanup.md`, executed task by task as written (no sub-phases, no new plan files).
**Status:** all ten tasks complete; close gate passed 2026-11-16. Delete-proposed list awaits Hamzi.

## H14 (resolved 2026-11-16)

No compliance labels at launch: no HIPAA, GDPR or SOC claims; Wavia may describe its factual controls (retention defaults, redaction, consented recording, erasure jobs, audit logs, data region). First hosting target: AWS me-central-1 (ECS/EC2, RDS PostgreSQL + pgvector, ElastiCache Redis, S3, KMS). Nothing deployed or bought.

## Commits

| Task | Commit | Outcome |
|---|---|---|
| 1 Telemetry | `be136ab` | Labelled counters/gauges/bucketed histograms with cardinality caps and percentiles; valid Prometheus exposition on every service; W3C spans with OTLP/HTTP export; turn latency, stage, barge-in, failover, drop, active-session metrics; session/turn/trace correlation in logs. Verified against a local OpenTelemetry Collector (15 spans and the `ucve_*` metrics landed). |
| 2 Readiness | `2cd4749` | `/health/live` vs `/health/ready` with bounded DB/Redis/profile/identity/capacity/VAD/Telnyx checks; provider readiness is configuration-only; draining is never ready; unknown runtime profile fails. |
| 3 Alerts | `f66576b` | Migration 034 `operational_alerts`; de-duplicated, escalating alerts with HMAC-signed webhook delivery recorded honestly; quota/capacity/provider-chain sources; Prometheus rules (promtool-validated); fake email and test-mode webhook success removed. |
| 4 Jobs | `6d22f33` | `worker_jobs.main` runner; migration 035 singleton slot claims; honest outcomes; dead-letter and repeated-failure alerts; image and compose service. Container drill: ready in 3 s, SIGTERM exit 0 in 1 s, restart did not re-run the claimed slot. |
| 5 Redaction | `a0a055d` | Process-wide log redaction (any logger, tracebacks); content keys dropped; international PII (cards with Luhn, IBAN, CNIC, Emirates ID, NRIC, Aadhaar, UK NI, Arabic/Urdu digits); transcript and speech previews removed from adapters. |
| 6 Retention / hold / erasure | `99f0db3` | Migration 036 (held state, append-only deletion trail); full-schema tenant erasure with object prefix sweep; customer API for legal hold, conversation deletion, workspace erasure, job status. Proven on PostgreSQL + S3-compatible storage. |
| 7 Load | `4236397` | Offline load harness. Found and fixed: Silero ONNX spinning all cores (460% → 6% of a core for the same load), fleet admission capped at one worker's capacity, unhandled exception on a missing provider credential. |
| 8 Shutdown / drills | `d2f78a8`, `e6102bb` | SIGTERM drain (drill: 503 draining, new session 1013, live call finished, exit 0); backup/restore drill (55 tables, 35 migrations, 48 policies identical). |
| 9 Cleanup | `efecac4` | `CLEANUP_CLASSIFICATION.md`: integrate / roadmap / archive / 8 delete-proposed. Nothing deleted. |
| 10 Runbooks | `efecac4`, `03b34aa` | Runbooks rewritten on real endpoints, metrics, alerts and commands; new deploy/drain and backup/restore runbooks. |

## Findings worth Hamzi's attention

1. **Post-call intelligence cannot run in production yet.** The leased queue and worker exist, but no concrete structured extraction/summary provider exists. The jobs runner reports it disabled with that reason. Stage 3 addresses it.
2. **No webhook-target management surface.** Tenants cannot configure post-call webhook targets through Studio or the API (repository code only). Stage 3.
3. **Latency under load.** On one Windows machine with mock providers, median reply time was ~0.83 s at 5 sessions per worker, ~1.36 s at 25 (standard profile) and ~1.57 s at 40. No drops or failures; the single event loop is the constraint. The standard profile's 25 sessions per worker should be treated as capacity, not an SLO-safe density, until measured on AWS hosts with real providers.
4. **Retained on erasure by design:** the tenant `audit_log` (immutable by trigger since migration 006), staff audit and support sessions, and the deletion record. They hold identifiers and actions, not conversation content. Revisit if compliance claims are added later.
5. **Staging compose OTEL endpoint** points at a non-existent `jaeger:4317` using the wrong protocol; not edited (deploy config), fix when the AWS deployment config is written (Phase 15 / H15).
6. **S3 behaviour** was proven against Adobe S3Mock (MinIO images are no longer pullable); real AWS S3 is unverified until an approved H15 check.
7. One intermittent failure in 1 of 6 full-suite runs during the gate, not reproduced in 8 stress runs of the new timing-sensitive tests or 4 further full runs.

## Next

Phase 15 (packaging and release qualification) — Stage 2 of Hamzi's 2026-11-15 instructions.
