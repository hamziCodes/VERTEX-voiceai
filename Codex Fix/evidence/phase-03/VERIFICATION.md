# Phase 03 Verification — First Audio and DSP

**Implementation date:** 2026-10-16
**Final verification rerun:** 2026-10-19
**Branch:** `wavia-fixv1`
**Provider mode:** offline fixtures and mock transports only
**Live calls / provider requests / charges:** none

## Root cause confirmed

The high first-audio delay was caused by orchestration differences, even when
the same vendors were selected:

1. The current pipeline waited for terminal punctuation, or a long nine-word
   clause, before submitting any text to TTS. The multilingual legacy path has
   an explicit first-chunk latency override and streams sentence callbacks as
   the LLM produces them.
2. The current Uplift adapter used `AsyncClient.post()` and read
   `response.content`, so no audio could leave the worker until the complete
   HTTP body arrived. The legacy Uplift service iterates the response body as it
   arrives on a pooled session.
3. The current egress converter resampled every provider chunk independently,
   resetting phase at every boundary. This causes sample drift and audible
   discontinuities for non-16 kHz providers.
4. Browser playout used an unexplained fixed 50 ms restart buffer while the
   server's 35 ms setting was unused.

## Implemented

- Added a lossless incremental multilingual speech chunker. The runtime
  `UCVE_CHUNKER_FIRST_WORDS` override is active; language profiles remain the
  fallback. Urdu and Arabic sentence terminators are supported, and
  punctuation-free output is bounded by a hard word limit.
- Normalized every stable speech chunk before TTS while retaining and
  normalizing the canonical complete assistant reply for transcript/history.
- Replaced Uplift full-body reads with streamed response iteration on its
  pooled `httpx.AsyncClient`.
- Added incremental RIFF/WAVE parsing, including split headers and non-audio
  chunks. Removed fixed pop-byte deletion so valid speech is not clipped.
- Made Uplift, Cartesia, and ElevenLabs emit the first even-aligned provider
  audio bytes immediately; configured batching applies after first audio.
- Added separate first-chunk, inter-chunk idle, and overall TTS deadlines.
- Prevented TTS retries after audio commit and emit a typed degraded-mode event
  instead of replaying speech. Empty/error streams no longer become fake
  successful silence.
- Bounded the LLM-to-TTS bridge, added cancellation-aware backpressure, queue
  age/high-water logging, and egress high-water/backpressure metrics.
- Added a continuous fractional-phase, windowed-sinc PCM16 resampler. It
  retains odd-byte carry and sample phase across arbitrary network chunks.
- Wired the server prebuffer recommendation into `audio_start`; the browser
  applies it unless a `prebuffer_ms` query override is present and reports its
  underrun count with playback acknowledgement.
- Removed obsolete pop-skip/client-chunk settings and documented the three TTS
  deadlines and final prebuffer behavior.

## Red-test evidence

The initial focused run failed during collection because
`StreamingSpeechChunker` and `StreamingEgressResampler` did not exist. After
their first implementation, 15 tests passed and the browser playout test still
failed because its buffer was fixed. After wiring the playout configuration,
all focused tests passed. A later partial-disconnect test exposed duplicate
audio because the failover router retried the same adapter after output commit;
the commit guard fixed that failure.

## Final automated verification

```text
pytest tests/latency/test_streaming_chunker.py tests/latency/test_tts_first_byte.py -q
14 passed

pytest tests/audio/test_streaming_resampler.py tests/audio/test_playout_buffer.py -q
9 passed

pytest tests/latency tests/providers -q
58 passed

pytest -q
485 passed, 1 skipped, 2 warnings
```

The two warnings are the existing tests that deliberately exercise short JWT
HMAC keys. The complete suite ran with `RUN_LIVE_PROVIDERS=0` and
`RUN_LIVE_DB_TESTS=0`.

```text
python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.
```

Ruff passes for every new Phase 03 module and test. The large existing pipeline
and two existing adapters retain pre-existing line-length/type-modernization
debt; the Phase 03 additions have no reported functional lint rules.

## Offline measurements

- Scripted latency corpus: 42 samples, 0 excluded, p50 1.1 ms, p95 19.6 ms,
  p99 23.2 ms. Artifact:
  `latency-baseline-20261016T134350283933Z.json`.
- Stateful 48 kHz to 16 kHz resampling of one second of PCM: 30.53 ms CPU time
  and exactly 32,000 output bytes in the recorded local run.
- DSP tests cover 8, 16, 22.05, 24, 44.1, and 48 kHz; odd byte boundaries;
  duration/sample drift; chunk-boundary equality; clipping; and rejection of a
  12 kHz out-of-band tone during 48 kHz to 16 kHz conversion.

Offline latency figures validate orchestration and measurement behavior. They
are not claims about vendor or Internet latency.

## Final-QA human gates retained

- Listen to English, Urdu, Arabic, and mixed-language speech for pronunciation,
  prosody, gaps, pops, speed, and clipped initial phonemes.
- Confirm whether the global two-word first chunk remains preferred for every
  language; the language profile value is used when the runtime override is
  disabled.
- Run the separately approved live Uplift/Cartesia/ElevenLabs comparison with a
  declared cost ceiling. No live comparison was attempted in this phase.
- Exercise real browser jitter and packet loss. Automated coverage verifies the
  scheduling contract and metrics, but does not replace an auditory browser
  session.

## Rollback

Revert the Phase 03 implementation commit. No database, schema, or external
provider migration is required. Restore the previous environment names only if
rolling back the code as well; the removed fixed-byte pop skip must not be used
with the new RIFF parser.
