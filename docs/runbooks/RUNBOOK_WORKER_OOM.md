# Runbook: Worker OOM

Phase 31 runtime profile tuning.

## Symptoms

- Kubernetes/container OOMKilled on worker-raw pods
- Silero pool initialization failures
- Admission rejecting despite quota available
- Elevated GC pauses before crash

## Immediate actions

1. Check `UCVE_RUNTIME_PROFILE` — high_density requires 16 GB RAM.
2. Reduce `max_sessions_per_worker` or switch dev → standard profile.
3. Verify `OMP_NUM_THREADS=1` set (habiba memory lesson).
4. Scale horizontally — add workers instead of raising per-worker cap.

## Memory model (Phase 17)

~150 MB base + ~50 MB Silero pool + ~3 MB/session

## Profile guidance

| Profile | max_sessions_per_worker | RAM |
|---|---|---|
| dev | 5 | 4 GB |
| standard | 25 | 8 GB |
| high_density | 40 | 16 GB |

## Escalation

SEV-2 if > 25% worker fleet restarting in 15 min.

## Prevention

- Load test before enabling high_density (Phase 33)
- Monitor `ucve_active_sessions` vs profile cap
