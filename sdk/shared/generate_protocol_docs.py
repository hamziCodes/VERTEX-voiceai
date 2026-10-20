"""Render the human realtime protocol reference from the canonical JSON schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "sdk" / "shared" / "event_schema.json"
DOC_PATH = ROOT / "docs" / "sdk" / "REALTIME_PROTOCOL.md"


def _required_payload(item: dict[str, Any]) -> str:
    payload = item.get("properties", {}).get("payload", {})
    required = payload.get("required", [])
    if required:
        return ", ".join(f"`{name}`" for name in required)
    if "$ref" in payload:
        return "schema-defined payload"
    return "none"


def render_protocol_document(schema: dict[str, Any]) -> str:
    """Return deterministic Markdown derived from the schema event inventory."""

    rows = []
    for item in schema["oneOf"]:
        event_type = item["properties"]["event_type"]["const"]
        direction = item["x-direction"].replace("_", " ")
        rows.append(
            f"| {direction} | `{event_type}` | {_required_payload(item)} |"
        )
    table = "\n".join(rows)
    version = schema["protocol_version"]
    supported = schema["supported_range"]
    return f"""# Wavia Realtime Protocol

> Generated from `sdk/shared/event_schema.json` by
> `sdk/shared/generate_protocol_docs.py`. Edit the schema, then regenerate this
> file; do not hand-edit the event inventory.

## Compatibility

- Current protocol: `{version}`
- Server-supported client range: `{supported}`
- Clients send `protocol.hello` as the first frame. The server answers
  `session.ready` before provider startup or rejects the connection with a
  typed `error` and WebSocket close code.
- Sequence numbers increase independently in each direction. `event_id` is
  unique per JSON frame. Unknown optional payload fields must be ignored within
  protocol v1.
- Breaking removals or payload reinterpretations require a new protocol major.

## Transport

- Endpoint: `ws://<worker>/ws/audio?token=<ephemeral-token>&protocol_version={version}`
- JSON control frames use the versioned envelope below.
- Binary media frames are signed 16-bit little-endian PCM, 16 kHz, mono.
- Provider query overrides are forbidden by default. They require an explicitly
  enabled development/test demo and are never part of the public SDK contract.

```json
{{
  "protocol_version": "{version}",
  "event_id": "unique-event-id",
  "sequence": 1,
  "event_type": "protocol.hello",
  "timestamp_ms": 0,
  "payload": {{}}
}}
```

## Event inventory

| Direction | Event | Required payload |
|---|---|---|
{table}

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
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    rendered = render_protocol_document(schema)
    if args.check:
        return 0 if DOC_PATH.read_text("utf-8") == rendered else 1
    DOC_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
