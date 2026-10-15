# Quarantine Manifest

| Date | Classification | Original path | Quarantine path | Size/hash or Git object | Reason | Verification |
|---|---|---|---|---|---|---|
| 2026-10-15 | generated cache | `.pytest_cache/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.pytest_cache/` | 5 files; 73,025 bytes | Disposable pytest state | System Python imports passed; latency suite 15 passed |
| 2026-10-15 | generated cache | `.ruff_cache/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.ruff_cache/` | 4 files; 1,214 bytes | Disposable Ruff state | System Python imports passed; latency suite 15 passed |
| 2026-10-15 | stale environment | `.venv/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.venv/` | 6,624 files; 228,637,662 bytes | Environment pointed to a stale interpreter; system Python is the working baseline | Canonical package imports passed; latency suite 15 passed |

The C01 quarantine contains 6,633 files and 228,711,901 bytes. It is ignored by Git and recoverable locally.

Secret files and raw key files are excluded from this program and must never appear in this manifest.
