# Runbook: backup and restore

## What must be backed up

- PostgreSQL (all tenant data, the migration ledger `schema_migrations`, audit and platform audit, alerts, job state).
- The recording/object store (`UCVE_RECORDING_S3_*`) if recordings are enabled.
- Secrets live outside the database (KMS/master key, environment secrets); back them up in the secret manager, never alongside the database dump.

Redis holds only short-lived admission leases, replay nonces and session token state; it is not backed up. After a Redis loss, active sessions continue and new admissions rebuild state.

## Logical backup and verified restore (portable)

```bash
pg_dump -Fc -d "$DATABASE_URL" -f wavia-$(date +%Y%m%dT%H%M).dump
createdb restored_check
pg_restore -d restored_check --exit-on-error wavia-<timestamp>.dump
python scripts/ops/db_fingerprint.py fingerprint "$SOURCE_URL" > before.json
python scripts/ops/db_fingerprint.py fingerprint "$RESTORED_URL" > after.json
python scripts/ops/db_fingerprint.py compare before.json after.json
python scripts/ops/db_fingerprint.py migrate "$RESTORED_URL"   # must apply 0
```

The drill `bash scripts/ops/drill_backup_restore.sh` runs all of this against a disposable database. Phase 14 result: 55 tables, 35 migrations (checksums), 48 RLS policies and all row counts identical; nothing pending after restore.

## Hosted backups

Managed snapshots and point-in-time recovery depend on the hosting target (decision H14). Until it is chosen, the logical dump above is the only verified procedure. Whatever the host, test a restore at least monthly with the fingerprint comparison.

## Privacy

Restoring an old backup can resurrect data that was later erased. After any restore, re-run privacy deletion for erasure requests completed after the backup time before the restored database serves traffic.
