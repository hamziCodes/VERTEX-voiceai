# Quickstart

Run Wavia locally end to end: control plane, voice worker, PostgreSQL and
Redis, with **mock providers** (no provider keys, no network calls, no cost).

---

## What you need

| Requirement | Why |
|---|---|
| Docker | Runs PostgreSQL, Redis and the Wavia images |
| Python 3.12 + [uv](https://docs.astral.sh/uv/) | Only for running services from source |
| Node 22+ | Only for the TypeScript SDK |

PostgreSQL is **required** whenever the control plane and worker run as
separate processes: the worker loads the session plan that the control plane
pinned in the database at mint time. In-memory repositories exist only for
tests inside a single process.

---

## 1. Start the stack (recommended: release images)

```bash
git clone <your Wavia repository> && cd VERTEX-voiceai
for s in control-plane worker-raw worker-jobs telephony-gateway; do
  docker build -f infra/docker/$s.Dockerfile -t wavia-$s:p15 .
done
bash scripts/release/container_stack.sh up
```

The script starts PostgreSQL (pgvector) and Redis, applies every migration
from the control-plane image, and waits until each service reports ready:

| Service | URL |
|---|---|
| Control plane | `http://127.0.0.1:28080` (`/docs`, `/health/ready`, `/demo/`) |
| Voice worker | `ws://127.0.0.1:28081/ws/audio` |
| Jobs runner | `http://127.0.0.1:28084/health/ready` |
| Telephony gateway | `http://127.0.0.1:28083/health/ready` |

Stop and remove everything with `bash scripts/release/container_stack.sh down`.

### From source instead (Linux or macOS)

```bash
uv sync --frozen
export DATABASE_URL=postgresql://...      # a migrated database
python -m infra.db.migrate --database-url "$DATABASE_URL"
export UCVE_ENV=development UCVE_DEMO_MODE=1 UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1
uv run uvicorn control_plane.app:app --port 8080 &
uv run python -m worker_raw.main            # port 8081
```

On Windows run the services in Docker: psycopg's async driver cannot use the
default Windows event loop that uvicorn starts.

---

## 2. Providers

`UCVE_ENV=development` uses mock speech, LLM and TTS providers, so no keys are
needed to try the pipeline. Live providers are opt-in (`RUN_LIVE_PROVIDERS=1`
or a production environment) and then require the matching credentials, which
tenants add as encrypted provider credentials in Studio
(`/v1/provider-credentials`). Never put provider keys in client code.

---

## 3. Open the demo console

`http://127.0.0.1:28080/demo/` mints a session, connects to the worker,
streams microphone audio and plays the reply.

---

## 4. Mint a session

Development demo mode (`UCVE_DEMO_MODE=1`) allows an unauthenticated mint for
a demo tenant and agent; they are created on first use:

```bash
curl -s -X POST http://127.0.0.1:28080/v1/session/mint   -H "Content-Type: application/json"   -d '{"tenant_id":"00000000-0000-0000-0000-000000000001","agent_id":"00000000-0000-0000-0000-0000000000a1"}'
```

The response carries `status`, `session_id`, `token` (single use),
`ttl_sec`, `ws_url`, `agent_config_version` and `session_plan_ref`.

Outside demo mode, mint from your backend with a tenant API key that has the
`session:mint` scope (`Authorization: Bearer <key>` on `/v1/session/mint`), or
with the HMAC-signed `POST /v1/session`. `/mint` is a legacy alias of
`/v1/session/mint`.

---

## 5. Use an SDK

Runnable quickstarts that mint, connect, send a text turn and receive agent
audio:

- Python: [`sdk/python/examples/quickstart.py`](../../sdk/python/examples/quickstart.py)
- TypeScript: [`sdk/typescript/examples/quickstart.mjs`](../../sdk/typescript/examples/quickstart.mjs)

```bash
python sdk/python/examples/quickstart.py --control-plane http://127.0.0.1:28080
```

A session token is spent when the WebSocket opens. If the worker rejects the
session the SDKs raise `SessionRejectedError` with the close code; mint a new
session to try again.

---

## 6. Connect a WebSocket directly

```javascript
const token = "<token from /v1/session/mint>";
const ws = new WebSocket(`ws://127.0.0.1:28081/ws/audio?token=${token}&protocol_version=1.0.0`);
ws.onopen = () => ws.send(JSON.stringify({
  protocol_version: '1.0.0',
  event_id: crypto.randomUUID(),
  sequence: 1,
  event_type: 'protocol.hello',
  timestamp_ms: Date.now(),
  payload: {
    protocol_version: '1.0.0',
    sdk: { name: 'quickstart', version: '1.0.0' }
  }
}));
```

Send raw 16-bit PCM16 audio (16 kHz, mono) as binary frames:
```javascript
ws.send(pcmArrayBuffer);
```

Receive binary PCM16 audio for playback, and JSON control events:
```javascript
ws.onmessage = (evt) => {
  if (evt.data instanceof ArrayBuffer) {
    // Play PCM16 audio
  } else {
    const event = JSON.parse(evt.data);
    console.log(event.event_type, event.payload);
  }
};
```

---

## Next Steps

- [Session Lifecycle →](./03-session-lifecycle.md)
- [WebSocket Protocol →](./04-websocket-protocol.md)
- [Provider Reference →](./05-providers.md)
