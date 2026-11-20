# Phase 03 — LLM-to-TTS First Audio and DSP

**Status:** READY FOR FINAL QA

**Goal:** Make the first safe text and real audio bytes flow immediately, with stream-aware deadlines and continuous high-quality resampling/playout.

**Depends on:** Phases 01–02.

**Audit coverage:** L01, L02 egress, L03, L04, L06, L08, P03 speech side.

## Human gate before implementation

Offline work needs none. Stop before any real provider comparison; request approval with expected cost. Hamzi may need to listen to prosody samples before the two-word rule becomes default for Urdu/Arabic.

## Files and interfaces

- Create or activate: `core/language/streaming_chunker.py` with `push(text_delta) -> list[SpeechChunk]` and `flush()`.
- Modify: `worker_raw/orchestration/pipeline.py`, split oversized responsibilities into focused turn/egress components if tests require it.
- Modify: `core/providers/adapters/uplift_tts.py`, provider timeout interfaces.
- Modify: `core/transport/resample_egress.py`, ingress resampler, browser worklet/playback.
- Create: `tests/latency/test_streaming_chunker.py`, `test_tts_first_byte.py`, `tests/audio/test_streaming_resampler.py`, `test_playout_buffer.py`.

## Tasks

- [x] Port the legacy first-chunk principle through the current LanguageProfile: first safe chunk target two words, then language delimiters/min/max limits; test punctuation-free Urdu/Arabic/English.
- [x] Normalize each emitted speech chunk before TTS while retaining a canonical full reply for transcript/context.
- [x] Replace current regex branch with the single tested chunker; remove or wire unused chunker settings so configuration affects behavior.
- [x] Change Uplift to streamed response reads on one pooled async client; parse RIFF/WAV chunks correctly or request raw PCM. Record real first network byte.
- [x] Give every provider three deadlines: connect/first chunk, inter-chunk idle, and overall. Remove whole-stream `wait_for(first_chunk_timeout)` semantics.
- [x] Define output-commit rules: failover allowed before any speech; after committed audio, emit typed interruption/repair behavior without replaying spoken text or tools.
- [x] Bound text/TTS/audio queues and expose queue age/high-water/underrun metrics. Backpressure must not deadlock LLM cancellation.
- [x] Implement stateful band-limited streaming resampling with fractional phase/carry across arbitrary chunks; validate duration, frequency response, clipping, and sample drift.
- [x] Align server chunk sizes/client prebuffer with measured jitter; the client acknowledges actual first scheduled/played turn audio.
- [x] Test slow first byte, slow middle chunk, partial disconnect, empty audio, WAV variants, cancellation, odd-byte boundaries, 8/16/22.05/24/44.1/48 kHz, and no punctuation.

## Verification

```powershell
python -m pytest tests/latency/test_streaming_chunker.py tests/latency/test_tts_first_byte.py -q
python -m pytest tests/audio/test_streaming_resampler.py tests/audio/test_playout_buffer.py -q
python -m pytest tests/latency tests/providers -q
```

Expected: first text emitted at configured safe boundary; streamed fake TTS audio reaches egress before response completion; no sample drift/discontinuity; timeouts identify stage; no duplicate audio on failure.

## Human verification

Hamzi listens to generated clips for naturalness, pronunciation, gaps, pops, speed, and clipped words. A live Uplift/Cartesia/ElevenLabs comparison is a separate approved V5 run.

## Exit criteria

- The current pipeline matches or beats the legacy orchestration path under the same offline delays.
- Uplift is genuinely streamed.
- Chunking config is active and multilingual.
- Audio continuity and perceived first-audio metrics pass without quality regression.
