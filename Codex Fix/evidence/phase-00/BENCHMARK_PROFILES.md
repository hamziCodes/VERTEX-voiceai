# Phase 00 benchmark profiles

## Web voice agent

- Reference operating system: Windows 11 Home 10.0.26300, build 26300.
- Reference CPU and memory: Intel Core i5-13420H, 15.6 GB RAM.
- Reference browser: Chrome 150.0.7871.115.
- Ingress contract: browser PCM/WebSocket path at 16 kHz mono PCM16 after client capture/normalization.
- User-perceived latency boundary: acoustic end of user speech through browser playback acknowledgement.
- Every manual run records microphone, output device, wired/USB/Bluetooth transport, power mode, and background load in its local artifact.

## Calling agent

- Intended carrier: Telnyx.
- Offline ingress contract: 8 kHz G.711 μ-law frames, carrier-sized packet timing, jitter/reordering cases, decode/resample to the engine's 16 kHz mono PCM16 contract.
- User-perceived latency boundary: caller acoustic end through the first audible outbound telephone sample.
- Phase 00 and later V0–V3 checks use fake carrier events and local codec/media simulation only.
- A real Telnyx sandbox call belongs to Phase 12 and requires a separate live/cost/destination approval.

The current audit found that the Telnyx webhook, media bridge, stable call identity, and full orchestrator lifecycle are incomplete. This profile defines the target measurement path; it is not evidence that live calling already works.

## Multilingual speech corpus

- FLEURS revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`, validation split.
- Two short clips each for US English, Pakistani Urdu, and Egyptian Arabic.
- Local fetch result: six mono 16 kHz PCM16 WAV files, 3.84–5.8 seconds each.
- License: CC BY 4.0. Audio and transcript manifest remain under the Git-ignored fixture directory.
- Code-switch timing fixture: the committed legacy `minglish_test.wav`, 16 kHz mono PCM16, 26.411 seconds. It cannot be used for word-error-rate acceptance until its reference transcript is confirmed.
