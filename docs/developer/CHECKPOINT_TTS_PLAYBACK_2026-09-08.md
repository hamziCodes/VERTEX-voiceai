# Checkpoint — Voice Pipeline Demo (2026-09-08)

**Status:** Server+client PCM confirmed loud; speaker routing hardened. Open in real Chrome/Edge.

## Confirmed by your 21:48 log

| Signal | Value | Meaning |
|--------|-------|---------|
| Worker Cartesia | `peak_abs` up to 1141 | Server has PCM |
| Client `AUDIO_IN` | **peak=16161**, rms=0.094 | Browser received loud PCM |
| `playCtx` | 48000Hz / running | Web Audio graph active |
| `playback_started` | sent | Scheduler ran |

So this is **not** STT/LLM/TTS failure. Audio is scheduled; output is not reaching your ears (OS device, tab mute, or **Cursor Simple Browser / embedded webview** which often has no speaker path).

## This pass

- Route Gain → **MediaStreamDestination + hidden `<audio>`** (and destination)
- Louder startup beep + **Test Speakers** button
- Hint to use Chrome/Edge

## Double-voice fix (2026-09-08 later)

Playback was connected to **both** `AudioContext.destination` and `<audio>` MediaStream → heard twice. Now **single path** via `<audio>` only. Hard-refresh demo (no worker restart needed for HTML). Restart worker to pick up Cartesia skip of punctuation-only scraps (`۔` 400s).

