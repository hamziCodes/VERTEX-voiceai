# Version compatibility matrix

What this release candidate was built and qualified with (Phase 15,
2026-11-16). "Qualified" means exercised offline in this repository's
release checks; live providers, carriers and cloud services are not yet
certified (see `Codex Fix/evidence/phase-15/LIVE_CERTIFICATION_PLAN.md`).

## Components

| Component | Version | Source of truth |
|---|---|---|
| Server (control plane, worker, jobs, telephony gateway) | 0.1.0 | `pyproject.toml`, FastAPI app `version` |
| REST API | `/v1`, OpenAPI document version 0.1.0 | `openapi.yaml` (generated from the app) |
| Realtime protocol | 1.0.0; server accepts `>=1.0.0 <2.0.0` | `core/protocol/realtime.py`, `sdk/shared/event_schema.json` |
| Database schema | migrations 001–036 (SHA-256 ledger) | `infra/db/migrations/` |
| Python SDK `ucve-voice-sdk` | 1.0.4 (protocol 1.0.0, `min_server_version` 0.1.0) | `sdk/python/ucve/version.py` |
| TypeScript SDK `@ucve/voice-sdk` | 1.0.4 (protocol 1.0.0, `minServerVersion` 0.1.0) | `sdk/typescript/package.json`, `src/client.ts` |
| Silero VAD model | v6.2.1, SHA-256 `1a153a22…88e3` | `core/vad/download_silero.py` |

## Runtimes and infrastructure

| Dependency | Qualified | Supported | Notes |
|---|---|---|---|
| Server Python | 3.12.16 (uv) / 3.12 slim image | 3.12 | `requires-python >=3.12`; images pin `python:3.12-slim@sha256:5e2bdb1b…` |
| Python SDK | 3.12 consumer venv | 3.10+ | Only dependency: `websockets>=12` |
| TypeScript SDK | Node 24.13 consumer | Node 22+ (global `WebSocket`), evergreen browsers | ESM only; React hook optional (`react>=18`) |
| PostgreSQL | 16 with pgvector (`pgvector/pgvector:pg16`) | 16 + pgvector | Required whenever services run as separate processes |
| Redis | 7 (`redis:7-alpine`) | 7 | Optional in development; required for multi-instance replay/admission state |
| Docker | Engine 29.9 (Docker Desktop 4.99) | Linux containers, amd64 | Images are amd64 only; not built for arm64 |
| Host OS for running services from source | Linux/macOS | Linux/macOS | Windows: run services in Docker (psycopg async cannot use the Proactor loop) |

## Compatibility rules

- An SDK talks to any server `>= min_server_version` that accepts its
  protocol version. Protocol 1.x changes are additive; a 2.0 protocol would be
  a new SDK major.
- Migrations are forward-only and, through 036, additive: the previous
  release (Phase 13, `b087147`, schema 033) runs unchanged against schema
  036, which is what makes image rollback safe (see `ROLLBACK.md`).
- Session tokens are single use and bound to the session plan pinned at mint;
  a rollback never changes the configuration of an in-flight session.
