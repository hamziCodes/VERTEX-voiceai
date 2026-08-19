# Phase 24: Latency Budget Enforcement and SLO Policies

## 1. Executive Summary & Core Logic

Formalize per-turn latency measurement, stage budget enforcement, and tenant-facing SLO policies — converting ad hoc `metric` WS events (v3/multilingual AUDIT_01/03 §4) and habiba SDK `metrics_updated` (AUDIT_04 §4) into structured `LatencyWaterfall` traces (File 9 §3.1). Extends Phase 06 `FailoverRouter` with **latency-based demotion** (File 3 §5.1 #4 — `[NEW]`, no legacy repo implements). Depends on Phase 07 observability, Phase 17 pipeline stage hooks, Phase 06 provider health state.

Target: **p50 <450 ms** cascaded TTFB design goal (File 1 §4) — measured, not assumed; realistic range 420–815 ms documented.

**v1 enforcement:** **warn-only** — emit metrics and logs on budget breach but do not hard-block turns or auto-demote unless tenant explicitly opts in via `SLOPolicy.enforce_demotion`. **Playback metric:** **client-reported audio-delivery completion** (`control.playback_started` from SDK), not TTS-first-byte. **S2S waterfall:** `[LATER]` per Phase 05 S2S stub.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `LatencyWaterfall` Pydantic model | File 9 §3.1 — one trace per turn |
| Stage budgets from File 1 §4 table | Design target with provenance |
| Rolling p50/p95 per provider | Phase 06 `ProviderHealthState.last_latency_ms` extension |
| Tenant `SLOPolicy` JSONB | Optional stricter budgets for enterprise |
| Client-reported playback timestamp | Measures caller experience, not server-side generation |
| Benchmark harness in `tests/latency-benchmarks/` | File 9 §3 — CI nightly optional |

**Reference docs:** blueprint File 01 §4; File 03 §5.1; File 09 §3; v3 `metric` WS events (AUDIT_01 §4).

## 3. What / How / Why

- **What:**
  - `LatencyWaterfall`: `{session_id, turn_id, vad_end_of_speech_ms, stt_final_ms, rag_retrieve_ms, llm_ttft_ms, chunker_ms, tts_ttfb_ms, playback_start_ms, total_e2e_ms}` — rag stage optional; **S2S variant `[LATER]`**
  - `StageBudget`: per-stage `{name, budget_ms, warn_ms}` from File 1 §4 defaults
  - `SLOPolicy`: tenant override — `{e2e_p50_target_ms, e2e_p95_target_ms, enforce_demotion: bool default false, alert_on_breach: bool}`
  - **`PlaybackMetricSource`:** SDK emits `control.playback_started` when first audio frame reaches AudioWorklet/output device — server records client timestamp; **do not use TTS first-byte as playback proxy**
  - `LatencyCollector`: subscribe to Phase 07 spans + Phase 17 stage callbacks + SDK playback events; emit unified `metric` WS event + Prometheus histogram
  - **`LatencyDemotionRule`:** if provider rolling p50 for stage exceeds budget for N turns (default 5) **and** `SLOPolicy.enforce_demotion=true`, demote in Phase 06 priority chain — **global default off in v1 (warn-only)**
  - `LatencyBenchmarkHarness`: scripted audio fixtures → mock/real providers → aggregate p50/p95/p99 report
  - Breach events → Phase 25 alerting hook (`LATENCY_SLO_BREACH` at warn severity)
- **How:** Phase 17 records monotonic timestamps at: VAD speech-end, STT final, RAG reconcile complete (if any), LLM first token, chunker output, TTS first byte. **Playback:** wait for client `control.playback_started` (Phase 28 SDK duty) with 2 s server-side fallback to TTS-first-byte **for logging gap only** — excluded from SLO gate. Collector computes deltas, compares to `StageBudget`, logs `latency.budget_exceeded{stage}` at **warn** severity. Demotion updates Phase 06 health state only when tenant opt-in. Benchmark harness runs outside hot path.
- **Why this approach:** File 1 §4 admits cascaded pipeline often exceeds 450 ms — measurement must precede tuning. **Hard enforcement rejected for v1** — no production variance baseline yet; matches Phase 06 demotion-not-hard-fail posture. **TTS-first-byte rejected for playback** — caller hears audio after network/buffering; client-reported delivery is ground truth.

## Deliverables

- `core/latency/__init__.py`
- `core/latency/waterfall.py` — `LatencyWaterfall`, `StageBudget`
- `core/latency/collector.py` — `LatencyCollector`
- `core/latency/slo_policy.py` — `SLOPolicy` loader from Phase 08
- `core/latency/demotion.py` — `LatencyDemotionRule` + Phase 06 integration (opt-in)
- `core/latency/playback.py` — client playback event handler
- `core/latency/budgets/default.yaml` — File 1 §4 table
- `tests/latency-benchmarks/harness.py`
- `tests/latency-benchmarks/fixtures/` — short audio clips per language
- `worker-raw/orchestration/latency_hooks.py` — timestamp injection points
- `docs/latency/S2S_WATERFALL_LATER.md` — stub pointer for Phase 05 S2S enablement

## 4. Compute & Resource Profile (if applicable)

Collector overhead: < 0.1 ms per stage timestamp. Histogram export: negligible. Benchmark harness: 10-turn fixture ~30 s with mock providers; real-provider nightly job ~5 min. Redis rolling window: last 20 turns per provider/category — ~1 KB.

## 5. Compliance Notes (if applicable)

Latency traces contain session/turn IDs only — no transcript text. Benchmark fixtures must use synthetic audio, not real caller recordings. SLO breach logs are operational metadata — Phase 12 audit optional at DEBUG.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **SLO enforcement mode:** **warn-only for v1** — demotion opt-in per tenant via `enforce_demotion`; no global hard enforcement without production baseline data.
2. **Playback_start_ms measurement:** **client-reported audio-delivery completion** (`control.playback_started`); TTS-first-byte diagnostic only.
3. **S2S path budgets:** **`[LATER]`** — separate waterfall when Phase 05 S2S enabled; cascaded schema only in v1.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_24_latency_slo.py`
- **Asserts:** waterfall computes correct deltas from mock timestamps; budget breach emits warn metric (not hard fail); demotion **does not** trigger when `enforce_demotion=false`; demotion triggers when opt-in true after N slow turns; SLOPolicy tenant override applied; harness produces p50/p95 report; playback uses client event timestamp; no PHI in trace payload.
- **Pass threshold:** 100% collector unit tests; harness completes 10-turn mock run.
- **Latency target:** collector adds < 1 ms p99 overhead per turn.
