# Wavia Realtime Protocol

> Generated from `sdk/shared/event_schema.json` by
> `sdk/shared/generate_protocol_docs.py`. Edit the schema, then regenerate this
> file; do not hand-edit the event inventory.

## Compatibility

- Current protocol: `1.0.0`
- Server-supported client range: `>=1.0.0 <2.0.0`
- Clients send `protocol.hello` as the first frame. The server answers
  `session.ready` before provider startup or rejects the connection with a
  typed `error` and WebSocket close code.
- Sequence numbers increase independently in each direction. `event_id` is
  unique per JSON frame. Unknown optional payload fields must be ignored within
  protocol v1.
- Breaking removals or payload reinterpretations require a new protocol major.

## Transport

- Endpoint: `ws://<worker>/ws/audio?token=<ephemeral-token>&protocol_version=1.0.0`
- JSON control frames use the versioned envelope below.
- Binary media frames are signed 16-bit little-endian PCM, 16 kHz, mono.
- Provider query overrides are forbidden by default. They require an explicitly
  enabled development/test demo and are never part of the public SDK contract.

```json
{
  "protocol_version": "1.0.0",
  "event_id": "unique-event-id",
  "sequence": 1,
  "event_type": "protocol.hello",
  "timestamp_ms": 0,
  "payload": {}
}
```

## Event inventory

| Direction | Event | Required payload |
|---|---|---|
| client to server | `protocol.hello` | `protocol_version`, `sdk` |
| server to client | `session.ready` | `protocol_version`, `supported_range`, `session_id` |
| server to client | `control.ping` | none |
| client to server | `control.pong` | none |
| client to server | `text.turn` | `text` |
| server to client | `transcript.partial` | schema-defined payload |
| server to client | `transcript.final` | schema-defined payload |
| server to client | `transcript` | schema-defined payload |
| server to client | `audio.start` | schema-defined payload |
| server to client | `audio.end` | `turn_id`, `generated_audio_ms` |
| client to server | `control.playback_started` | `turn_id`, `client_playback_started_ms` |
| client to server | `control.barge_in` | `sequence` |
| server to client | `control.clear_audio` | `turn_id`, `sequence` |
| client to server | `control.clear_audio_ack` | `turn_id`, `sequence`, `played_audio_ms` |
| client to server | `control.playback_drained` | `turn_id`, `played_audio_ms` |
| server to client | `assistant.played_text_commit` | `turn_id`, `text`, `played_audio_ms`, `complete` |
| server to client | `metric.latency` | `kind`, `turn_id`, `durations_ms` |
| server to client | `session.token_expiring` | `expires_at_ms`, `refresh_url` |
| bidirectional | `session.close` | `code`, `reason`, `retryable` |
| server to client | `error` | schema-defined payload |
| server to client | `degraded` | schema-defined payload |

`transcript.partial` may be superseded by later partials for the same turn;
`transcript.final` is never silently dropped. Binary audio following
`audio.start` belongs to that turn until `audio.end`. On interruption, clients
must clear scheduled audio and answer `control.clear_audio` with
`control.clear_audio_ack`; uninterrupted playback ends with
`control.playback_drained`.

## Keepalive, expiry, close, and retry

Clients answer `control.ping` with `control.pong`. A missed heartbeat closes the
session. `session.token_expiring` instructs the host application to mint or
refresh an ephemeral token; raw credentials never travel through the SDK.
`session.close.payload.retryable` decides whether a reconnect may be attempted.
SDK connection attempts use capped exponential backoff and never retry forever.
Protocol v1 does not promise mid-session resume, so a reconnect creates a new
media connection and must not replay microphone audio automatically.

## Compatibility aliases

The worker temporarily accepts `barge_in`, `text_turn`, `user_turn`, `ping`,
`pong`, `playback_started`, `audio_start`, `audio_end`, `transcript`, and
`degraded_mode` while v1 clients migrate. Public SDKs emit canonical names.
Aliases are removed only in the next protocol major and produce a deprecation
signal where the runtime can safely do so.
