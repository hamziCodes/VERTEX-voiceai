# Phase 14 — Operations, Compliance, and Cleanup

**Status:** COMPLETE (offline) 2026-11-16 — evidence in `Codex Fix/evidence/phase-14/`; delete-proposed list awaits Hamzi

**Goal:** Make production operations truthful: readiness, telemetry export, alerts, jobs, resource limits, privacy, retention, recovery and clearly classified unfinished/dead code.

**Depends on:** Phases 09–12.

**Audit coverage:** I01 operations, I04 modes, I09–I11, I13 jobs, L11 scaling, dead-code list.

## Human gate before implementation

Resolve H14. Compliance labels are product/legal commitments; code primitives alone do not authorize HIPAA/GDPR claims.

## Files and interfaces

- Modify: observability exporters/metrics/readiness, runtime profiles, Compose services, worker jobs and runbooks.
- Modify: structured logging/redaction and compliance storage integrations.
- Create: job lease/scheduler contracts, dependency readiness tests, resource/load profiles and cleanup classification report.

## Tasks

- [ ] Export real traces/metrics/logs with bounded cardinality; implement histogram buckets/percentiles and session/turn correlation without PII.
- [ ] Split liveness from readiness; check DB/Redis/runtime plan/provider readiness appropriately without paid probe requests.
- [ ] Wire alerts to real SLO/quota/provider/DLQ/job failures and persist configuration securely.
- [ ] Repair monthly quota, stale lease, DLQ retry, KB and retention jobs with durable leases/idempotency; deploy/schedule them in documented topology.
- [ ] Apply recursive logging redaction and remove transcript/provider-body previews by default; test international PII and nested structures.
- [ ] Prove legal hold, retention and erasure with chosen durable stores and audit failure semantics.
- [ ] Load-test worker startup/concurrency, shared VAD/model resources, queue bounds, memory, CPU and event-loop lag against runtime profiles.
- [ ] Define graceful shutdown/drain, rolling compatibility, provider outage and restore/backup drills.
- [ ] Classify every cleanup candidate as integrate, roadmap/quarantine, archive/exclude, or delete-proposed. Do not delete without separate approval.
- [ ] Update runbooks using actual commands and signals.

## Verification

```powershell
python -m pytest tests/observability tests/compliance tests/jobs tests/scaling -q
```

Add offline load/soak and container readiness commands at execution time. Expected: exported spans/metrics in local collector, jobs survive retries/restarts, readiness fails on required dependencies, no sensitive nested log fields, resource limits meet selected profile.

## Human intervention

Hamzi approves hosting/compliance claims and any deletion list. External monitoring accounts or production load tests require separate approval.

## Exit criteria

- No scheduled job is a no-op or fake success.
- Health/alerts/metrics correspond to real system state.
- Compliance behavior matches approved scope and evidence.
- Cleanup is reviewable and non-destructive until approved.
