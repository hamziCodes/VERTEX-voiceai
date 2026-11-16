# Wavia 0.1.0-rc1 — release candidate notes

**Status:** release candidate, qualified offline only. Not published, not
deployed. Live providers, carriers and cloud services are certified only
after Hamzi approves each step in
`Codex Fix/evidence/phase-15/LIVE_CERTIFICATION_PLAN.md`.

**Branch:** `wavia-fixv1` · **Server** 0.1.0 · **Realtime protocol** 1.0.0 ·
**SDKs** 1.0.4 · **Schema** migrations 001–036 · versions in
[COMPATIBILITY.md](COMPATIBILITY.md).

## What is in this release

**Voice engine (phases 00–08)**
- Native WebSocket voice pipeline: Silero VAD (pinned v6.2.1), streaming STT,
  LLM and streamed TTS, with end-of-speech → first-audible-sample latency
  telemetry per turn.
- Deterministic barge-in: played-text commits, client clear/drain, owned
  teardown.
- Realtime protocol v1 with Python and TypeScript SDKs (generated types).
- Immutable, hashed session plans pinned at mint; signed, single-use session
  tokens; tenant-bound mint with replay protection.
- Strict provider catalogue, tenant-scoped provider credentials and
  stream-safe failover.

**Platform (phases 09–13)**
- PostgreSQL with row-level security per tenant, checksummed migrations,
  durable usage and quotas, Redis leases.
- Knowledge bases: bounded ingestion, local embeddings, pgvector retrieval.
- Post-call records, review, redaction, retention and signed webhook delivery.
- Telnyx inbound and controlled outbound telephony.
- Studio (self-serve dashboard): workspaces, roles, invitations, agents with
  versioned publishing, API keys, provider credentials, conversations, usage,
  platform staff roles and audited read-only support sessions.

**Operations and compliance (phase 14)**
- Bounded Prometheus metrics, W3C traces with OTLP export, readiness vs
  liveness, draining on SIGTERM.
- De-duplicated operational alerts with signed webhook delivery.
- Dedicated jobs runner with singleton slots and honest outcomes.
- Process-wide log redaction including international identifiers.
- Legal hold, conversation deletion and workspace erasure with an
  append-only deletion trail.

**Packaging and qualification (phase 15)**
- Every service image builds from a clean checkout, installs only the
  hash-pinned export of `uv.lock`, runs as a non-root user and passes
  readiness against PostgreSQL and Redis.
- Generated OpenAPI document (71 routes) served from the running app.
- SDK wheel, sdist and npm tarball install into isolated consumers and run
  their quickstarts against the release images.
- Release drills, guarded live-certification scripts, rollback plan and
  compatibility matrix.

## Fixed in the release candidate

- Container access logs no longer raise logging errors (redaction kept the
  log-argument shape).
- SDKs no longer retry a session the worker already rejected; they raise
  `SessionRejectedError` with the close code.
- The migration CLI runs on Windows.
- pypdf 6.21.4 and opentelemetry-api 1.45.2 fix 8 published advisories.
- The provider ping script no longer puts a key in a URL.
- The telephony gateway rejects a malformed Telnyx public key at startup
  instead of reporting ready and failing every real webhook.
- Found by the release drills:
  - Losing the database no longer freezes the control plane; every service
    answers a JSON 503 with `Retry-After` within ~5 s (was a plain-text 500
    after 30 s), and pooled connections are checked before reuse.
  - A Redis outage is reported as unavailable (503 / WebSocket 1013), never
    as a nonce replay or an invalid token, and revocations are never
    silently dropped; Redis clients have timeouts and idle health checks.
  - The worker closes with the retryable 1013 (with a reason) when the
    database, admission store or cluster capacity is the problem, instead of
    4401 "invalid session" or a normal 1000.
  - Migration checksums no longer depend on whether the image was built from
    a Windows or a Linux checkout.

## Known limitations

- **No live certification yet:** live STT/LLM/TTS quality, cost and real
  latency; carriers; AWS S3/KMS/RDS/ElastiCache; registry publishing.
- **Latency:** offline numbers measure pipeline overhead with scripted
  providers only (42 samples: p50 5 ms, p95 62 ms, p99 68 ms). On one
  Windows machine with mock providers the standard profile reached its 25
  sessions per worker at a median reply of ~1.36 s; treat it as capacity, not
  an SLO-safe density, until measured on AWS.
- **Post-call intelligence** has its queue and worker but no structured
  extraction/summary provider; the jobs runner reports it disabled.
- **Webhook targets** cannot yet be configured from Studio or the API.
- **Managed (LiveKit) worker** is a roadmap placeholder; its readiness always
  fails by design.
- **Images are amd64 only.** Services run natively on Linux/macOS; on Windows
  run them in Docker.
- **Compliance:** no HIPAA, GDPR or SOC claims (H14). Retained on erasure by
  design: tenant audit log, staff audit, support sessions, deletion records.
- **Studio final screenshot approval** (Phase 13 exit 8) is pending.
- **Package names** still use the `ucve` prefix; renaming must happen before
  the first public publish.
