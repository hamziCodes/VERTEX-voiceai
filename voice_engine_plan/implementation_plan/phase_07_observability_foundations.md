# Phase 07: Observability Foundations (Logs, Metrics, Traces)

## 1. Executive Summary & Core Logic

Establish structured logging, per-call correlation IDs, metrics emission, and trace span hooks before pipeline integration (Phase 17) and telephony work. Formalizes ad hoc `metric` WS events from v3/MULTI (`legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/transport/websocket.py`) and habiba SDK `metrics_updated` passthrough into one schema consumed by workers, control plane, and future dashboards. Enables debuggable Phase 17+ integration tests.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `structlog` + JSON renderer | Structured, grep-friendly, OpenTelemetry-compatible |
| OpenTelemetry SDK (traces + metrics) | Industry standard; export to OTLP/collector later |
| `call_id` / `session_id` / `tenant_id` context vars | Per-call correlation across async tasks |
| Prometheus-compatible counters/histograms | Self-host friendly; no vendor lock-in |

**Reference docs:** blueprint File 09 §3.1 latency waterfall; OpenTelemetry Python docs; v3/MULTI metric event names.

## 3. What / How / Why

- **What:** `ObservabilityContext` (contextvars), `get_logger()` binding session fields, standard log schema (`timestamp`, `level`, `event`, `call_id`, `tenant_id`, `phase`, `latency_ms`, `provider_id`, `error_code`). Metrics: `ucve_turn_latency_ms`, `ucve_barge_in_total`, `ucve_provider_failover_total`, `ucve_buffer_drop_total`. Trace spans: `session.connect`, `turn.stt`, `turn.llm`, `turn.tts`, `barge_in.commit`. Wire-compatible `metric` control event for SDK consumers (File 08 §3).
- **How:** Middleware on control-plane requests sets correlation ID (Phase 13 auth middleware attaches `tenant_id`). Worker session start generates `call_id` (UUID). All pipeline stage boundaries emit span start/end + structured log line via Phase 07 helpers. **Log redaction processor** strips PHI patterns **and auth leakage** before emit: phone, email, SSN patterns **plus** query-string params `token`, `api_key`, `signature`, `access_token`, `jwt` (Phase 13 WS auth uses `?token=` on WSS — proxy/access logs must never persist session JWTs). Apply redaction to URL fields, `http.url`, and unstructured message strings at INFO+. **OTel SDK initialized now** but **exporter disabled** (`OTEL_EXPORTER_ENABLED=false`) until Phase 30 collector deploys — spans/metrics accumulate in-process for tests. **Log sink:** stdout JSON (container-first); optional file rotation handler for local dev only (`UCVE_LOG_FILE`, not production default). **Metrics exposition:** `/metrics` on **control-plane only** for v1, protected by Phase 13 auth — workers emit metrics via logs/traces until multi-worker scrape is needed.
- **Why this approach:** Building Phase 17 without correlation IDs forces printf debugging and rework. Central observability module avoids each adapter inventing log formats. Alternative: only stdout logging — insufficient for multi-tenant production ops.

## Deliverables

- `core/observability/__init__.py`
- `core/observability/context.py` — contextvars, `ObservabilityContext`, bind/clear helpers
- `core/observability/logging.py` — structlog config, `get_logger()`, PHI + auth-param redaction processors
- `core/observability/metrics.py` — metric registry + counters/histograms
- `core/observability/tracing.py` — OTel tracer setup, span helpers
- `core/observability/events.py` — `MetricEvent` wire shape for transport emission
- `core/observability/schema.json` — documented log field contract
- `control-plane/metrics.py` — Prometheus `/metrics` route (auth-gated in Phase 13)

## 4. Compute & Resource Profile (if applicable)

Structured log overhead: ~50–100 μs per log line. Metrics: in-memory registry; negligible until high cardinality (guard label sets: no unbounded `agent_id` as metric label — use logs/traces). OTel batch exporter: default batch 512 spans, flush 5 s — add < 5 MB RAM per worker.

## 5. Compliance Notes (if applicable)

HIPAA/GDPR: logs and traces are compliance artifacts. Default log pipeline must redact known PHI patterns (phone, email, SSN) **and strip auth query params** (`token`, `api_key`, `signature`) at emit time for INFO+ — critical once Phase 13 enables WSS `?token=` auth. Audit log stream (Phase 12) is separate from debug logs — do not merge. Retention defaults: app logs 30 days, audit 7 years placeholder (Phase 11 sets policy).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **OTel:** structlog + OTel wired now; exporter disabled until Phase 30 collector.
2. **Log sink:** stdout JSON primary; file rotation dev-only convenience.
3. **`/metrics`:** control-plane only for v1, behind Phase 13 auth — not per-worker.
4. **Auth param redaction:** strip `token`/`api_key`/`signature` query params from all log URL fields (Phase 13 dependency).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_07_observability.py`
- **Asserts:** context propagation across async tasks; log output contains `call_id`; metric counter increments; span created for mock pipeline stage; PHI redaction strips sample phone number; **URL with `?token=secret` redacted in log output**.
- **Pass threshold:** 100% observability unit tests; sample JSON log validates against `schema.json`.
- **Latency target:** logging wrapper overhead < 0.2 ms p99 per call site.
