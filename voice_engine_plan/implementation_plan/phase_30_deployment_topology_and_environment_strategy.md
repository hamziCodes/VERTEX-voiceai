# Phase 30: Deployment Topology and Environment Strategy

## 1. Executive Summary & Core Logic

Define deployable topology for UCVE: single-node `docker compose` product path (File 9 §4.2 Tier 0–1), multi-service Kubernetes/Helm scale path, and environment promotion strategy (dev → staging → prod). Harvests habiba's proven multi-Dockerfile service split (`legacy_codebases/habiba-sdk-agent/docker/{worker,control-plane,admin,tenant-portal-api}.Dockerfile`, AUDIT_04 §1) and fixes multilingual's undeclared torch/numpy Docker gap (AUDIT_03 §2 — **explicit torch in worker-raw image**). v3 had no Dockerfile (Render `render.yaml` only, AUDIT_01 §1) — UCVE containerizes properly.

Depends on Phase 00 monorepo layout, Phase 07 OTel (exporter enabled here), Phase 08 Postgres/Redis, Phase 13 secrets via env/vault refs, Phase 28 control-plane OpenAPI host.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `docker compose` single-node default | File 9 §4.2 — documented tested product install |
| Per-service Dockerfiles under `infra/docker/` | habiba separation pattern |
| Python 3.12-slim control-plane; 3.12 worker with torch declared | AUDIT_03 fix + habiba worker tuning |
| Helm charts `[LATER]` scaffold only in v1 | Scale path without blocking compose |
| Env-specific `.env.*.example` | No secrets in repo |
| GitHub Actions CI from habiba extended | AUDIT_04 §1 — only legacy repo with in-repo CI |

**Reference docs:** blueprint File 09 §4; habiba `.github/workflows/ci.yml`; File 01 §3.3 Redis session state.

## 3. What / How / Why

- **What:**
  - **`infra/docker/docker-compose.yml`** — services: `postgres`, `redis`, `control-plane`, `worker-raw`, `telephony-gateway` (optional profile), `minio` (S3 dev stub)
  - **Dockerfiles:** `control-plane.Dockerfile`, `worker-raw.Dockerfile`, `telephony-gateway.Dockerfile`, `worker-managed.Dockerfile` (optional LiveKit, not required)
  - **worker-raw requirements:** **explicit `torch`, `numpy`, Silero deps** — do not repeat multilingual undeclared-deps failure (File 9 §4.1, AUDIT_03 §2)
  - **Environment tiers:** `dev` (compose, mock providers OK), `staging` (real provider sandbox keys, Phase 09 vault), `prod` (HA Postgres, Redis, ≥2 provider routes enforced at deploy check)
  - **`infra/docker/.env.example`** + `docs/deploy/ENVIRONMENT_MATRIX.md` — var ownership per service
  - **Phase 07 OTel:** set `OTEL_EXPORTER_ENABLED=true` in staging/prod compose overlays; OTLP endpoint configurable
  - **Health checks:** `/health` on control-plane + worker readiness (Redis + Postgres connectivity)
  - **CI workflow stub:** `.github/workflows/ci.yml` — lint, phase_tests, docker build smoke
  - **Helm:** `infra/helm/ucve/` chart skeleton — `[LATER]` full values; documented in `docs/deploy/KUBERNETES.md`
- **How:** `docker compose up` brings sovereign demo (native WS, no LiveKit). Staging uses Telnyx sandbox + DirectSIP profile. Prod checklist validates Phase 06 ≥2 routes, Phase 09 no inline secrets, Phase 18 DirectSIP path green. Deploy docs cross-link Phase 31 resource profiles.
- **Why this approach:** File 1 §3.6 requires sovereign path without LiveKit. Habiba's Dockerfile split is production-proven. **Undeclared torch rejected** — breaks Silero VAD (Phase 17). Alternative: PaaS-only like v3 Render — insufficient for self-host compliance tenants.

## Deliverables

- `infra/docker/docker-compose.yml`
- `infra/docker/docker-compose.staging.yml` — overlay
- `infra/docker/control-plane.Dockerfile`
- `infra/docker/worker-raw.Dockerfile` — torch/numpy explicit
- `infra/docker/telephony-gateway.Dockerfile`
- `infra/docker/worker-managed.Dockerfile` — optional
- `infra/docker/.env.example`
- `docs/deploy/ENVIRONMENT_MATRIX.md`
- `docs/deploy/COMPOSE_QUICKSTART.md`
- `docs/deploy/KUBERNETES.md` — Helm scaffold pointer
- `.github/workflows/ci.yml` — extended monorepo CI stub

## 4. Compute & Resource Profile (if applicable)

Single-node compose minimum: **4 vCPU / 8 GB RAM** (Phase 17 estimate for ~10 concurrent sessions). Postgres: 2 GB RAM dev. Redis: 512 MB. worker-raw: `OMP_NUM_THREADS=1` per habiba AUDIT_04 §5 memory notes.

## 5. Compliance Notes (if applicable)

Prod env matrix documents encryption: Postgres TLS, S3 SSE, Redis AUTH. Secrets only via Phase 09 vault refs or sealed secrets — never in compose files committed to git. HIPAA prod requires BAA on all cloud subprocessors listed in deploy checklist.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Default install path:** **`docker compose` single-node** — Helm scaffold only; full K8s values `[LATER]`.
2. **worker-raw base image:** **Python 3.12 with explicit torch/numpy** — fix multilingual Docker gap; not 3.11-slim without ML deps.
3. **LiveKit in compose:** **optional profile `livekit`** — default compose stack runs with `UCVE_ENABLE_LIVEKIT=false` (Phase 18).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_30_deployment_topology.py`
- **Asserts:** docker-compose.yml defines required services; worker-raw Dockerfile installs torch; health check endpoints documented; ENVIRONMENT_MATRIX covers dev/staging/prod; COMPOSE_QUICKSTART references Phase 17 WS; CI workflow file exists; LiveKit optional not default.
- **Pass threshold:** 100% structural deploy artifact checks.
- **Latency target:** N/A; docker build smoke < 10 min CI (when enabled).
