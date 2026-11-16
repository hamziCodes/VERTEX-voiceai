# Phase 15 — qualification by deployment model

Each model is qualified separately, offline, against the release candidate on
`wavia-fixv1`. "Not included" lists what a customer of that model must not be
promised yet.

## 1. Packaged SDK (Python `ucve-voice-sdk` 1.0.4, TypeScript `@ucve/voice-sdk` 1.0.4)

| Check | Result |
|---|---|
| Wheel, sdist and npm tarball build from a clean checkout | PASS (`scripts/release/qualify_sdks.sh`; SHA-256 in `hamza_local/phase15/clean/sdk/SHA256SUMS`) |
| Install into an isolated consumer (fresh venv / fresh npm project outside the source tree) | PASS — only the built artifact, nothing from the repository |
| Documented quickstart runs: mint → connect → text turn → streamed agent audio | PASS for both, against the release-image stack |
| TypeScript build, 6 unit tests, `npm audit` | PASS; 0 vulnerabilities |
| Python SDK unit tests (`tests/sdk`) | PASS |
| Rejection is not retried with a spent token; `SessionRejectedError` carries the close code | PASS (fixed in `cc92722`) |

**Not included:** registry publication (H15 L6); package names still `ucve`
(rename decision before publishing); no LICENSE file in the repository; SDK
version 1.0.4 vs server 0.1.0; Flutter and LiveKit SDKs are roadmap only;
audio capture/playback helpers beyond PCM16 framing; a published reference
site for the SDK.

## 2. Managed enterprise deployment (Wavia operates the containers)

| Check | Result |
|---|---|
| All five images build from a clean checkout, hash-pinned dependencies, digest-pinned base, non-root | PASS (no-cache build of `dd66f09`; rebuilt at the final head) |
| Migrations 001–036 from the control-plane image on empty PostgreSQL + pgvector | PASS |
| Readiness (`/health/ready`) of control plane, worker, jobs runner, telephony gateway | PASS, all within 2 s |
| Upgrade from the previous release schema (033 → 036) with data | PASS — ledger and checksums kept, rows kept, re-run idempotent |
| Rollback: previous release code (`b087147`) on the upgraded schema | PASS — healthy and minting |
| Redis restart | PASS — honest retryable 503/1013 for the first use of each stale connection, then sessions resume |
| SIGKILL of worker and control plane | PASS — ready again in ≤ 3 s, sessions resume |
| Database network loss | PASS — readiness 503, liveness keeps answering, mint 503 in ~5 s, recovery in seconds |
| Graceful drain on SIGTERM; backup/restore; privacy erasure on PostgreSQL + S3-compatible storage | PASS (Phase 14 drills, re-run in Phase 15: privacy proof) |
| Disposable-database, Redis and S3 test matrix | PASS — 61 + 1 + 1 (+ privacy proof) |
| Dependency vulnerabilities (pip-audit) / licences | 0 known vulnerabilities; licences permissive except psycopg (LGPL-3.0, unmodified library) for sign-off |

**Not included:** any hosted environment (AWS me-central-1 is chosen, nothing
provisioned); real S3/KMS/RDS/ElastiCache; live STT/LLM/TTS; carriers; TLS,
ingress, autoscaling policies and secrets management on the host; arm64
images; the managed (LiveKit) worker, which is a roadmap placeholder; latency
under production load; post-call intelligence (no extraction provider); alert
delivery to a real receiver.

## 3. Self-serve dashboard (Studio)

| Check | Result |
|---|---|
| `npm ci` from the lockfile | PASS |
| Typecheck, lint (zero warnings), 223 unit tests | PASS |
| Production build (`next build`) | PASS |
| `npm audit --omit=dev` | 0 vulnerabilities |
| Control-plane API for Studio (workspaces, roles, invitations, agents, publishing, API keys, credentials, conversations, usage, platform staff, support sessions) | PASS in the offline suite and disposable-database tests |

**Not included:** a Studio container image or hosting; sign-in uses WorkOS
AuthKit, which needs a WorkOS environment (not configured, not exercised end
to end here); Phase 13 exit 8 (Hamzi's screenshot approval) is pending;
webhook-target management screens; the customer journey from the website
through sign-up to a live call — that is Stage 3's checkup.
