# Phase 15 verification

**Close gate:** 2026-11-16, Windows 11, Python 3.12.16 (uv, frozen lock),
Node 24.13, Docker Desktop 4.99 (engine 29.9). Flags: `UCVE_ENV=test`,
`RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_TELEPHONY=0`. No live provider, carrier,
registry, deployment or paid service was contacted. The only network use was
package downloads (PyPI, npm, Docker Hub) and advisory lookups (pip-audit,
npm audit).

**Release candidate commit:** `fb40fc6` (final clean-checkout run).

## Commands and results

| Check | Result |
|---|---|
| `python -m pytest tests voice_engine_plan/tests/phase_tests -q` | PASS — 1171 passed, 21 skipped (the 21 are the disposable-service tests below) |
| `bash scripts/release/run_live_db_tests.sh` (tests/db + h3 persistence on disposable PostgreSQL) | PASS — 61 passed, 1 skipped (the S3 test, covered by the privacy proof); teardown 0 containers/volumes |
| Live Redis test on disposable Redis | PASS — 1 passed |
| `bash scripts/ops/run_privacy_proof.sh` (PostgreSQL + Adobe S3Mock) | PASS |
| No-cache build of all five images from a clean worktree (`dd66f09`) | PASS — control-plane 967 s (dependency download), others reuse the layer |
| Clean worktree rebuild at `fb40fc6` | PASS — image IDs below |
| `container_stack.sh` on the clean images: migrations 001–036, readiness | PASS — control plane 1 s, worker 0 s, jobs 0 s, telephony 3 s |
| `scripts/release/qualify_sdks.sh` on the clean images | PASS — Python wheel and TS tarball installed into isolated consumers; quickstarts received 9600 / 3200 bytes of agent audio |
| `scripts/release/drills.sh` on the clean images | PASS — all 18 checks (below) |
| Studio `npm ci`, typecheck, lint, 223 unit tests, `next build` | PASS |
| TypeScript SDK build + 6 tests | PASS |
| `pip-audit` on `requirements/runtime.txt` | PASS after fix — 8 advisories (pypdf ×7, opentelemetry-api ×1) resolved by 6.21.4 / 1.45.2 |
| `npm audit --omit=dev` (Studio, TS SDK) | 0 vulnerabilities |
| Licence report inside the control-plane image | 59 distributions; all permissive except psycopg/psycopg-binary/psycopg-pool (LGPL-3.0, unmodified) — needs Hamzi's sign-off |
| `export_requirements.sh --check`, `export_openapi.py --check` | PASS |
| Offline latency corpus (`python -m tests.latency.baseline --repetitions 3`, commit `3cefc0e`) | 42 samples, p50 5.0 ms, p95 62.1 ms, p99 68.1 ms — scripted providers, pipeline overhead only |

### Clean images (`fb40fc6`)

| Image | ID |
|---|---|
| wavia-control-plane | `sha256:c9929cbde7dd73d40523459c9b87d96bb1796d2915293120d076f274180a2c77` |
| wavia-worker-raw | `sha256:b4d8e065f13cebf1f482df53fb26f03bf7dd5274e4eadc5562c9fa631e13c753` |
| wavia-worker-jobs | `sha256:7dab21c4946bb70ebe3eb8fe446cae5daa0f34380bfb55424f59ede637777eaf` |
| wavia-telephony-gateway | `sha256:95018a85b0da83d09cd391de594c32c998a348cb998385ea1614b717b16db7c9` |
| wavia-worker-managed | `sha256:f5c5172f36504d11bcefc19840ce7ea9bba26100877f277da3eee4dfb80633bb` |

Base: `python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`. Each image is 654 MB.

### SDK artifacts (SHA-256)

| Artifact | SHA-256 |
|---|---|
| `ucve_voice_sdk-1.0.4-py3-none-any.whl` | `4adf913eba9216e8215fec5a76fe1a8af7c5eebfb9003ca98a2cb18f15c4cfab` |
| `ucve_voice_sdk-1.0.4.tar.gz` | `df789965064120d8b31adc27ceec3242b0f83217db0e70da30c4416e67208e3e` |
| `ucve-voice-sdk-1.0.4.tgz` | `fdba78b85f5fab814feb188edde09227e159fa10de17ffd98ca3603d4e79ea52` |

The archives embed build timestamps, so hashes differ between builds of the same commit; publish exactly the bytes that were qualified.

### Drills (clean images, `fb40fc6`)

| Drill | Result |
|---|---|
| Upgrade 033 → 036 with data | ledger unchanged (33 entries, checksums equal); 36 after; rows kept; re-run finds nothing pending |
| Rollback: `b087147` code on schema 036 | healthy in 14 s; mints against upgraded data |
| Redis restart | ready in 1 s; first use of each stale connection answers a retryable 503/1013; real session on attempt 5 (about 8 s) |
| SIGKILL worker + control plane | ready in 3 s / 2 s; real session afterwards |
| Database network loss | readiness 503 in 10 s; liveness keeps answering; mint 503 `DATABASE_UNAVAILABLE` in 5 s; ready 5 s after recovery; real session afterwards |

## Failure-first notes

Every fix in this phase has a regression test that was run against the old
code and failed first (logging, SDK retry ×2, Telnyx key, session-store
outage, worker DB/admission close codes, migration line endings). The drills
themselves were the first failing evidence for the outage fixes: the first
full drill run failed rollback (a drill bug: the previous release has no
`/health/ready`), Redis (false 401 replay) and network (15 s freeze, 30 s
plain 500); later runs found the CRLF checksum mismatch and the 1000
"session ended" admission close.

## Not verified

Live providers and real latency, carriers, AWS services, registry publishing,
any hosted deployment, arm64 images, Studio sign-in through a WorkOS
environment, alert delivery to a real receiver. See
`LIVE_CERTIFICATION_PLAN.md`.
