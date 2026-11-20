# Phase 14 cleanup classification

**Status:** classification only. **Nothing has been deleted.** The `delete-proposed` list below needs Hamzi's explicit approval, item by item or as a batch; until then every file stays where it is.

Builds on `Codex Fix/codebase-cleanup/C05_CLASSIFICATION.md` (2026-10) and re-checks each candidate against the code as of Phase 14 (`git grep` of production packages `control_plane core worker_raw worker_jobs worker_managed telephony_gateway post_call`, plus `tests/` and `voice_engine_plan/tests/`).

Classes:

- **integrate** — real behaviour that should be wired in or merged with its live counterpart.
- **roadmap / quarantine** — intentionally incomplete capability; keep, never advertise or schedule until built.
- **archive / exclude** — reference material; keep in the repository but out of packages, images and test discovery.
- **delete-proposed** — no production caller, superseded or a fake; removal proposed, with what must change alongside it.

## Delete-proposed (needs Hamzi's approval)

| # | Path | Why | Production callers | Test/plan callers that would change |
|---:|---|---|---|---|
| D1 | `worker_jobs/quota_monthly_reset.py` | Monthly usage is derived from the ledger (`date_trunc('month', NOW())` in `core/db/repos/usage_pg.py`); there is nothing to reset. Phase 14 made it refuse to report success. | none (not scheduled) | `tests/jobs/test_scheduler.py` (asserts it refuses) |
| D2 | `worker_jobs/quota_stale_sweeper.py` | Built an empty in-memory tracker and always returned 0; Redis admission scripts already expire stale leases atomically. | none (not scheduled) | `tests/jobs/test_scheduler.py` |
| D3 | `worker_jobs/dlq_retry_sweeper.py` + `core/errors/dlq.py` | In-memory DLQ with an asyncpg-style fire-and-forget insert (wrong driver, swallowed errors). Production dead letters live in `post_call_jobs`, `webhook_deliveries` and `privacy_deletion_jobs`, which retry themselves and are observed by `queue_observer`. | none | `voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py` (two DLQ tests) |
| D4 | `core/errors/alert_router.py` | Superseded by `core/alerts` (durable, de-duplicated, signed delivery). Phase 14 removed its fake successes; nothing in production calls it. | none | `tests/hardening/test_remediation_r1_r7.py`, phase 25 test |
| D5 | `control_plane/metrics.py` | `/metrics` now renders through `core/observability/http.render_metrics`; `handle_metrics_request` has no caller. | none | one hardening test imports it |
| D6 | `worker_jobs/purge_retention.py` | Older parallel retention path: synchronous platform-role `DELETE FROM sessions` only, no recordings/objects, no audit. Superseded by `retention_enqueue` + `privacy_deletion` (durable leases, object-then-row deletion, legal-hold checks). | none (not scheduled) | `tests/hardening/test_h4_compliance.py` |
| D7 | `core/providers/chain_resolver.py` | No importer anywhere (production or tests). Routing is resolved by `core/providers/routing.py` and the session plan. | none | none |
| D8 | `costing/` (2 Markdown files) | Pricing/infrastructure analysis notes; no code or doc references. Could move to `docs/archive/` instead of deletion — Hamzi's call (commercial content). | none | none |

## Integrate

| Path | Decision |
|---|---|
| `core/compliance/erasure.py`, `core/compliance/legal_hold.py` | Older in-memory erasure/legal-hold helpers re-exported by `core/compliance/__init__.py`; `erasure.py` calls `run_until_complete` inside async code. Merge into the durable privacy-job path when the H14-scoped legal-hold/erasure task runs, then propose deletion. |
| `worker_raw/handlers/session_lifecycle.py` | Phase 17 lifecycle contract (tests only). Consolidate with `worker_raw/ws_session.py`. |
| `core/latency/benchmarks/` | Population aggregation now lives in `LatencyCollector` and the exported histograms; keep for Phase 15 latency corpus, then fold or remove. |
| `post_call` intelligence worker | Real leased queue; blocked on a structured extraction/summary provider (none ships). Stage 3 adds one; until then the jobs runner reports it disabled. |
| `infra/docker/docker-compose.staging.yml` OTEL endpoint | Points at `jaeger:4317` with no such service and the wrong protocol (exporter is OTLP/HTTP on 4318). Not edited (deploy config); fix when the hosting target (H14) is chosen. |

## Roadmap / quarantine

| Path | Decision |
|---|---|
| `worker_managed/` | LiveKit managed runtime is roadmap-only (H05). Readiness now reports not-ready so it can never take traffic. Keep the image surface. |
| `worker_raw/telephony/inbound_handler.py` | Phase 18 tests only; live path is `telephony_gateway`. Keep, non-production. |
| LiveKit, Twilio, PTA, Qdrant, WhatsApp adapters | Named provider boundaries; never advertised until implemented and tested. |
| `sdk/flutter`, `sdk/typescript-livekit` | Roadmap SDKs (H05); exclude from Phase 15 artifacts. |

## Archive / exclude

| Path | Decision |
|---|---|
| `legacy_codebases/` (917 files, 23 MB) | Read-only comparison material. Already excluded from pytest; Phase 15 must keep it out of wheels, images and build contexts (`.dockerignore`). The load harness reads one committed WAV from it as a speech fixture; copy that clip into `tests/` before any archive move. |
| `docs/archive/` | Historical evidence. Keep. |
| `voice_engine_plan/` | Root pytest collects its phase tests (`pyproject.toml` testpaths, CI). Keep. |
| `agent-studio/` (README only), `worker-raw/`, `control-plane/` (hyphenated shims) | Required by `test_phase_00_monorepo_baseline.py` / phase 27 tests. Removing them means changing those plan tests; not proposed now. |
| `schemas/agent-config-v1.json`, `openapi.yaml` | `openapi.yaml` is served at runtime (`control_plane/openapi_serve.py`); the JSON schema is referenced by docs and a phase 26 test. Phase 15 regenerates both from runtime contracts. |
| `AUDIT.md` | Source audit; documentation only. Keep. |
| `hamza_local/` | Ignored local evidence (screenshots, load reports, drills). Never committed. |

## Fixed in Phase 14 instead of classified

Fake successes removed in place (no deletion needed): the alert email channel, test-env webhook success, DLQ "retried" count, quota job success messages, static `/health` used as readiness, the managed worker's "ok".
