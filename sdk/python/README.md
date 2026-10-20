# Wavia Python Voice SDK

The Python SDK connects a trusted application to Wavia's v1 raw-WebSocket
realtime protocol. Obtain an ephemeral session token from your authenticated
host backend. Never embed provider keys or the host mint secret in a client.

```python
from ucve import UCVEVoiceClient

client = UCVEVoiceClient(token=session_token, ws_url=worker_ws_url)
await client.connect()
await client.send_text_turn("Hello")
await client.disconnect()
```

The v1 wire format is 16 kHz, mono, signed 16-bit little-endian PCM. The SDK
performs the protocol handshake, answers keepalives, reports interruption
playback acknowledgements, and surfaces typed error/degraded/expiry events.
