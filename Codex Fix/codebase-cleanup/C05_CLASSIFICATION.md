# C05 Stub, Roadmap, and Reference Classification

This phase distinguishes removable code from incomplete capabilities that still have executable, documentation, packaging, or roadmap consumers.

| Candidate | Evidence | Decision |
|---|---|---|
| `core/latency/benchmarks/` | Operational latency runbook names `LatencyBenchmarkHarness`; Phase 01 needs a population aggregator | Keep and repair/replace through truthful latency telemetry |
| `worker_raw/handlers/session_lifecycle.py` | Imported by `test_phase_17_pipeline_integration.py`; represents Phase 17 lifecycle contract | Keep; consolidate with `ws_session.py` in lifecycle remediation |
| `worker_raw/telephony/inbound_handler.py` | Imported by Phase 18 tests; current production-upgrade plan assigns its full pipeline integration | Keep; treat as incomplete and non-production until telephony phase |
| `core/providers/chain_resolver.py` | Resilience intent is required by provider-routing plan even though active runtime wiring is absent | Keep; wire into immutable session plan in provider phase |
| `worker_jobs/quota_monthly_reset.py` | No-op today, but represents required quota operation | Keep, never schedule/claim success until implemented |
| `worker_jobs/quota_stale_sweeper.py` | Creates process-local tracker; insufficient for distributed quota release | Keep as incomplete; replace with shared-store job |
| `worker_jobs/dlq_retry_sweeper.py` | Increments attempts without dispatching jobs | Keep as incomplete; do not schedule as successful retry |
| `worker_jobs/kb_ingestion.py` | Audit found incompatible RAG interfaces and false persistence behavior | Keep disabled; repair with RAG phase contract |
| `worker_jobs/purge_retention.py` | Partial retention behavior, missing complete tenant/storage deletion semantics | Keep disabled for production until compliance phase |
| `worker_managed/` | Docker image and optional LiveKit deployment consume it | Keep; it is an optional deployment surface |
| LiveKit, Twilio, PTA, Qdrant, WhatsApp adapters/stubs | Named provider/roadmap boundaries | Keep outside advertised usable capabilities until implemented and tested |
| `legacy_codebases/` | Requested comparison implementations for latency investigation | Keep read-only and outside packages/tests/build contexts |
| `docs/archive/` | Historical implementation/audit evidence | Keep as archive |
| `voice_engine_plan/` | Root pytest collects its phase tests | Keep |
| `agent-studio/` | Phase tests and product roadmap reference it | Keep |

## Result

No tracked runtime candidate in this group is safely removable without breaking a test, plan, deployment surface, or required future capability. C05 therefore performs no tracked source deletion. This is a safety result, not an assertion that the retained code is production-ready.

The product documentation and capability registry must distinguish these states:

- implemented and production-tested;
- implemented but offline-only or incomplete;
- roadmap/not available.

The production remediation phases own the corresponding implementation work. Cleanup must not erase those contracts to make the tree appear smaller.

## Generated artifacts

Python bytecode under active packages is ignored and safe to quarantine after the final C06 verification. It is not moved before testing because the verification run will recreate it.
