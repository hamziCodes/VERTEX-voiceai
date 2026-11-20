# WebSocket Protocol

The canonical, generated v1 protocol reference is
[`../sdk/REALTIME_PROTOCOL.md`](../sdk/REALTIME_PROTOCOL.md). Its source is
`sdk/shared/event_schema.json`; the synchronization test fails if the generated
document drifts.

The worker multiplexes versioned JSON control envelopes and binary 16 kHz mono
PCM16 frames on `/ws/audio`. A client must send `protocol.hello` before audio.
Provider overrides are excluded from the public connection contract and are
accepted only when an operator explicitly enables the local development demo.
