# Phase 12C Verification Evidence

**Date:** 2026-10-28

**Branch:** `wavia-fixv1`

**Implementation commit:** `61ea1e7`

**Result:** PASS

## Delivered behavior

- Added strict typed Telnyx media frames for `connected`, `start`, `media`,
  `dtmf`, `mark`, `stop`, and `error` events. Malformed or unsupported frames
  fail closed.
- Media socket admission verifies Telnyx Ed25519 over the exact configured
  stream URL and timestamp before any call media is accepted.
- Start frames bind the socket to the expected Telnyx call-control ID and stream
  ID. Codec negotiation accepts only PCMU, 8 kHz, mono.
- Inbound base64 PCMU is decoded, statefully upsampled, and rebuffered into exact
  20 ms 16 kHz PCM frames while preserving sequence, chunk, timestamp, and
  synthetic-loss metadata.
- Outbound 16 kHz PCM is statefully low-pass downsampled, encoded to PCMU,
  emitted as 160-byte 20 ms payloads, and paced by a monotonic clock.
- Ingress and egress queues are bounded. Backpressure, playback clear, partial
  buffers, carrier stop, unexpected disconnect, protocol failure, and worker
  callback failure have deterministic cleanup behavior.
- Reordering is bounded for long calls. Duplicate and late chunks are dropped,
  bounded loss is filled with PCMU silence, and excessive gaps fail closed.
- Metrics expose byte/frame counts, loss/duplicate/late/silence/clear/discard
  counts, maximum queue depths, and ingress/egress processing p95 values. Audio
  and phone numbers are not logged or retained.
- Raw SIP/RTP and LiveKit remain outside the v1 carrier media path.

The protocol shape follows Telnyx's official Voice API media-streaming contract:
PCMU at 8 kHz mono, base64 RTP payloads without RTP headers, bidirectional media,
clear messages, and asynchronous mark/DTMF/error events. Source:
<https://developers.telnyx.com/public/llms/calling/voice-api-full.txt>.

## Failure-first evidence

The new media test initially failed during collection because the adapter module
did not exist. After the first implementation, a clear/backpressure test exposed
a race between queued audio and the carrier send lock. The adapter now uses a
generation boundary and serialized socket writes so stale queued frames are
discarded around clear without deadlocking a slow sink.

Additional close-gate tests were then added for DTMF/mark handling, partial
egress discard, unexpected carrier disconnect, callback failure, and bounded
reorder history. These tests passed without weakening any failure policy.

## Automated verification

### Focused and related offline regression

```powershell
py -3.12 -m pytest tests/telephony/test_telnyx_media.py tests/audio voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12c-related-final
```

Result: **40 passed** in 2.39 seconds.

The generated-audio/fake-clock cases cover exact duration conservation,
arbitrary fragmentation, deterministic reorder/loss/duplicate behavior, bounded
long-call history, 20 ms packet cadence, 160-byte PCMU output, bounded queue
depth, clear/backpressure behavior, call and stream identity, codec rejection,
DTMF/mark handling, disconnect/failure cleanup, and zero leaked worker tasks.

### Full forced-offline suite

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12c-full-final
```

Result: **900 passed, 12 skipped, 2 warnings** in 12.49 seconds. The warnings
are the existing intentionally short invalid HMAC fixtures in
`tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and scoped lint: **passed**.
- Scoped mypy: **5 source files passed**.
- Python compilation: **passed**.
- `git diff --check`: **passed**.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- Windows `%SystemDrive%` test-cache artifacts were moved intact into ignored
  `hamza_local` directories; nothing was committed or deleted.

## Boundaries and next exact action

- No environment file, raw key file, Telnyx account, carrier endpoint, provider,
  shared database, destination number, deployment, paid traffic, or live call was
  accessed.
- Phase 12C proves the transport boundary with generated audio and a fake
  carrier. It does not yet wire that transport through VAD, STT, LLM, tools, TTS,
  metering, or post-call finalization.
- Begin Phase 12D with failure-first fake-carrier and fake-provider tests proving
  one nonempty inbound voice turn through VAD → STT → LLM → TTS → paced carrier
  egress. Then prove barge-in, duplicate-hangup idempotency, exact usage/post-call
  finalization, and cleanup across carrier/provider/worker failures. Do not
  contact Telnyx or live providers.
