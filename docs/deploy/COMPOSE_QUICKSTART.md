# Compose Quickstart

Single-node UCVE install (Phase 30 Tier 0–1).

## Requirements

- Docker 24+ and Compose v2
- 4 vCPU / 8 GB RAM minimum (~10 concurrent sessions)

## Steps

1. ```bash
   cd infra/docker
   cp .env.example .env
   # Edit POSTGRES_PASSWORD and vault refs
   ```

2. ```bash
   docker compose up -d --build
   ```

3. Wait for health checks:
   - control-plane: `http://localhost:8080/health`
   - worker-raw: `http://localhost:8081/health`

4. Open API docs: `http://localhost:8080/docs` (Phase 28).

5. Run sovereign WS test — see Phase 17 pipeline integration and [../developer/QUICKSTART_HOST_BACKEND.md](../developer/QUICKSTART_HOST_BACKEND.md).

## Optional profiles

- `telephony-gateway` — add when testing inbound PSTN (Phase 18)
- LiveKit profile — **not default**; set `UCVE_ENABLE_LIVEKIT=true` only when needed

## Scaling

Apply runtime profile via `UCVE_RUNTIME_PROFILE` — see [../../infra/scaling/profiles/](../../infra/scaling/profiles/) and Phase 31 docs.

## Troubleshooting

- worker-raw OOM → lower profile or add workers ([../runbooks/RUNBOOK_WORKER_OOM.md](../runbooks/RUNBOOK_WORKER_OOM.md))
- torch/Silero load failures → verify worker-raw image built with explicit torch (File 9 §4.1)
