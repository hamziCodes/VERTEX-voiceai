# UCVE Realtime Audio and Event WebSocket Protocol

## Transport and connection

- Endpoint: `ws://<host>:8081/ws/audio?token=<JWT>&stt_provider=...&llm_provider=...&tts_provider=...`
- Authentication: ephemeral mint token issued by `POST /v1/session/mint`.
- Multiplexing: one WebSocket carries binary PCM audio and JSON control frames.

## Audio framing contract

- Encoding: raw signed 16-bit little-endian PCM (`pcm_s16le`).
- Sample rate: 16,000 Hz.
- Channels: one (mono).
- Transport: binary WebSocket frames. The worker slices accepted ingress chunks into its canonical internal frame size.

## Control and telemetry events

| Direction | Event | Required payload | Meaning |
|---|---|---|---|
| Client to server | `pong` or `control.pong` | optional client timestamp | Heartbeat response |
| Client to server | `control.playback_started` | `turn_id`, client performance timestamp and clock domain | Correlated actual playback onset |
| Client to server | `control.playback_drained` | `turn_id`, `played_audio_ms` | Confirms all scheduled speech for the turn reached the speaker |
| Client to server | `control.clear_audio_ack` | `turn_id`, monotonic `sequence`, `played_audio_ms` | Confirms interruption cleared client playout and reports the played boundary |
| Client to server | `control.barge_in` | `turn_id`, monotonic `sequence`, optional energy metadata | Canonical interruption request; bare `barge_in` remains an inbound compatibility alias |
| Client to server | `text.turn`, `text_turn`, or `user_turn` | text | Text turn that bypasses STT |
| Server to client | `ping` | interval | Liveness heartbeat |
| Server to client | `audio_start` | `turn_id`, server send timestamp and clock domain | Identifies the turn for following audio |
| Server to client | `transcript` | speaker and text | User or agent transcript |
| Server to client | `metric` with `kind: latency` | versioned latency payload | Raw timestamps, valid durations, missing reasons, queue state and population percentiles |
| Server to client | `control.barge_in` | `turn_id`, monotonic `sequence`, reason | Signals a committed interruption |
| Server to client | `control.clear_audio` | `turn_id`, monotonic `sequence`, reason | Requires immediate client buffer clear and acknowledgment |
| Server to client | `audio_end` | `turn_id`, generated audio duration | Marks the last server audio frame for a turn |
| Server to client | `assistant.played_text_commit` | `turn_id`, text, played duration, completeness | Reports the assistant text admitted to conversation history |

The primary user metric is acoustic end-of-speech to playback acknowledgement receipt using the server monotonic clock. It is labeled `server_ack_upper_bound` because it includes acknowledgement network delay. Client `performance.now()` values stay in the client clock domain and are never subtracted from server timestamps.

Missing anchors remain `null` and appear in `missing_reasons`. The server does not substitute, cap, or invent stage durations. SLO evaluation remains provisional until production measurements establish contractual targets.

The canonical machine-readable contract is `sdk/shared/event_schema.json`.

The bare inbound `barge_in` alias is deprecated until the next protocol major;
the worker emits a `protocol_deprecation` info event when it is used.

The client must stop scheduled sources on `control.clear_audio` and return
`control.clear_audio_ack`. The server commits assistant context only through the
PCM boundary reported by that acknowledgment. On an uninterrupted turn, the
client sends `control.playback_drained` after receiving `audio_end` and rendering
all scheduled sources; only then does the session return to `LISTENING`.
