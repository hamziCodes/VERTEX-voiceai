# Phase 05: Provider Interface Contracts (VAD/STT/LLM/TTS/S2S)

## 1. Executive Summary & Core Logic

Define enforced abstract interfaces for every swappable AI provider category so orchestration code never imports Gladia, Groq, or Uplift directly. Generalizes habiba's registry-facing adapters (`legacy_codebases/habiba-sdk-agent/worker/providers/`) and MULTI's unused protocols (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/core/interfaces.py`) into one contract layer in `core/providers/interfaces/`. S2S interfaces are declared but feature-flagged off by default.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `abc.ABC` + Pydantic v2 config models | Blueprint File 03 §2; validation at adapter boundary |
| `AsyncIterator` for streaming STT/LLM/TTS | Matches all legacy streaming patterns |
| `CancellationToken` from Phase 02 | TTS must honor cancel at every yield (File 02 §3.3) |
| Separate config vs runtime state objects | Prevents habiba capability/adapter remap drift (AUDIT_04 §6) |

**Reference docs:** blueprint File 03 §2–3; habiba `capabilities.py` and `registry.py`.

## 3. What / How / Why

- **What:** `BaseVADProvider`, `BaseSTTProvider`, `BaseLLMProvider`, `BaseTTSProvider`, `BaseSpeechToSpeechProvider` with paired config/event models (`VADConfig`, `STTConfig`, `Transcript`, `LLMConfig`, `LLMStreamChunk`, `TTSConfig`, `S2SConfig`, `S2SEvent`). `ProviderCapabilityStatus` enum. `ToolDefinition` for LLM/MCP alignment.
- **How:** One module per category under `core/providers/interfaces/`. Orchestrator imports only these ABCs. Concrete adapters live in `core/providers/adapters/` (stub `Null*` implementations for tests in this phase). STT defaults: `code_switching=False`, `endpointing_seconds=0.2`. LLM includes `history_token_budget` (replaces legacy list-length prune). **TTS adapters emit audio at provider-native sample rate** (e.g. 22050 Hz from Uplift per `legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/services/uplift_service.py`); `TTSConfig.sample_rate` documents native output. **Resampling to 16 kHz (WebSocket) or 8 kHz (telephony) happens once at the transport boundary** using Phase 01 `Resampler` — not inside each adapter. **S2S:** full ABC + `NullS2SProvider` stub only; no live provider registers against it until post-MVP.
- **Why this approach:** MULTI proved interfaces alone are insufficient if orchestrator bypasses them (AUDIT_03 §6). Declaring ABCs before adapters forces mypy/ruff import-linter rules in Phase 06 registry. Alternative: plugin entry points only — rejected; explicit registry + capability table is habiba's production pattern.

## Deliverables

- `core/providers/__init__.py`
- `core/providers/interfaces/__init__.py`
- `core/providers/interfaces/vad.py`
- `core/providers/interfaces/stt.py`
- `core/providers/interfaces/llm.py`
- `core/providers/interfaces/tts.py` — includes `native_sample_rate` on streamed chunks metadata
- `core/providers/interfaces/s2s.py`
- `core/providers/interfaces/capability.py` — `ProviderCapabilityStatus`, `ProviderCapabilityEntry`
- `core/providers/adapters/null_vad.py` — no-op test adapter
- `core/providers/adapters/null_stt.py`
- `core/providers/adapters/null_llm.py`
- `core/providers/adapters/null_tts.py`
- `core/providers/adapters/null_s2s.py`

## 4. Compute & Resource Profile (if applicable)

Interface layer only — negligible runtime cost. Null adapters: < 0.01 ms per call for CI smoke tests.

## 5. Compliance Notes (if applicable)

Config models must not accept raw API keys — credentials resolved via Phase 09 vault at adapter construction. `Transcript.text` and LLM message bodies are PHI-capable; interfaces must not define default logging of these fields.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **S2S interface:** define full contract now as stub (`NullS2SProvider`); no provider implements against it yet.
2. **TTS sample rate:** provider-native output; single resample at transport boundary (Phase 01 `Resampler`; wired in Phase 17/18), not per-adapter.
3. **`Transcript.confidence`:** remains optional — legacy Gladia paths never populated it (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/core/interfaces.py`).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_05_provider_interfaces.py`
- **Asserts:** each ABC cannot be instantiated without required methods; null adapters pass `health_check()`; config validation rejects empty language lists; TTS stream honors cancel token mid-iteration.
- **Pass threshold:** 100% interface contract tests; mypy strict on `core/providers/interfaces/` clean.
- **Latency target:** N/A (contract tests only).
