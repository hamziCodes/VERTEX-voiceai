# Quarantine Manifest

| Date | Classification | Original path | Quarantine path | Size/hash or Git object | Reason | Verification |
|---|---|---|---|---|---|---|
| 2026-10-15 | generated cache | `.pytest_cache/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.pytest_cache/` | 5 files; 73,025 bytes | Disposable pytest state | System Python imports passed; latency suite 15 passed |
| 2026-10-15 | generated cache | `.ruff_cache/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.ruff_cache/` | 4 files; 1,214 bytes | Disposable Ruff state | System Python imports passed; latency suite 15 passed |
| 2026-10-15 | stale environment | `.venv/` | `hamza_local/clean_codebase/generated/2026-10-15-c01/.venv/` | 6,624 files; 228,637,662 bytes | Environment pointed to a stale interpreter; system Python is the working baseline | Canonical package imports passed; latency suite 15 passed |
| 2026-10-15 | unused tracked test harness | `tests/latency-benchmarks/harness.py` | `hamza_local/clean_codebase/tracked/latency-harnesses/tests-latency-benchmarks/harness.py` | Git blob `75be50e3fc41b086799aff8d3f443de873a94514` | Duplicate of the retained runtime-era harness; no active import or collected test | Latency suite 15 passed; 70 targeted tests collected; canonical Ruff passed |
| 2026-10-15 | empty tracked test package | `tests/latency_benchmarks/__init__.py` | `hamza_local/clean_codebase/tracked/latency-harnesses/tests-latency_benchmarks/__init__.py` | Git blob `d47fa439c4b6cb1046211ec64d74b0055ade71a7` | Parallel empty package with no imports or tests | Latency suite 15 passed; 70 targeted tests collected; canonical Ruff passed |
| 2026-10-15 | generated cache | `tests/latency-benchmarks/__pycache__/` | `hamza_local/clean_codebase/tracked/latency-harnesses/tests-latency-benchmarks/__pycache__/` | 1 generated `.pyc` | Cache belonging to quarantined duplicate | Source directory removed after move |
| 2026-10-15 | generated cache | `tests/latency_benchmarks/__pycache__/` | `hamza_local/clean_codebase/tracked/latency-harnesses/tests-latency_benchmarks/__pycache__/` | 1 generated `.pyc` | Cache belonging to quarantined duplicate | Source directory removed after move |

The C01 quarantine contains 6,633 files and 228,711,901 bytes. It is ignored by Git and recoverable locally.

Ruff recreated its cache during C02 verification. That regenerated ignored cache was moved to `hamza_local/clean_codebase/generated/2026-10-15-c01/.ruff_cache-post-verification/`; no tracked file was involved.

Secret files and raw key files are excluded from this program and must never appear in this manifest.
