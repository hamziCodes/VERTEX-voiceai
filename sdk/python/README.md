# Wavia Python Voice SDK

The Python SDK connects a trusted application to Wavia's v1 raw-WebSocket
realtime protocol (Python 3.10+, one dependency: `websockets`).

```bash
pip install ucve-voice-sdk   # or the wheel from a release bundle
```

## Quickstart

1. Your backend mints a short-lived session with a tenant API key that has
   the `session:mint` scope:

   ```http
   POST /v1/session/mint
   Authorization: Bearer <tenant API key>
   Content-Type: application/json

   {"tenant_id": "<tenant id>", "agent_id": "<published agent id>"}
   ```

   The response contains `token` (single use) and `ws_url`.

2. The client connects with that token only:

   ```python
   from ucve import SessionRejectedError, UCVEVoiceClient

   client = UCVEVoiceClient(
       token=session["token"],
       ws_url=session["ws_url"],
       on_transcript=lambda speaker, text: print(speaker, text),
       on_audio=lambda pcm16: player.write(pcm16),
   )
   try:
       await client.connect()
   except SessionRejectedError as exc:
       print("worker refused the session:", exc.code, exc.reason)  # mint again
       raise
   await client.send_text_turn("Hello")
   await client.disconnect()
   ```

A complete runnable example, including the mint call against a local
development engine, is in [`examples/quickstart.py`](examples/quickstart.py).

Never embed provider keys, tenant API keys or the host mint secret in a
client. The v1 wire format is 16 kHz, mono, signed 16-bit little-endian PCM.
The SDK performs the protocol handshake, answers keepalives, reports
interruption playback acknowledgements, and surfaces typed
error/degraded/expiry events. Connection attempts are retried only while the
worker is unreachable; once the socket opens the token is spent.
