# API Reference — Control Plane

The **Control Plane** (`control_plane/app.py`) is a FastAPI application serving the Wavia management REST API on port **8000**.

Interactive API docs available at: `http://localhost:8000/docs`

---

## Authentication

### Demo Mode (`UCVE_ENV=development`)
The `/mint` endpoint is unauthenticated. All other management endpoints require an API key bearer token.

### Production
- **Session minting** (`/v1/session`): HMAC-SHA256 signed request
- **Management endpoints** (`/v1/usage`, `/v1/audit`, etc.): `Authorization: Bearer ucve_live_<key>`
- **Metrics** (`/metrics`): `Authorization: Bearer <UCVE_METRICS_BEARER>`

---

## Endpoints

### Health

#### `GET /health`
Returns control plane readiness status.

**Response:**
```json
{"status": "ok", "service": "control-plane"}
```

---

### Session Management

#### `POST /mint` · `POST /v1/session/mint`
**Development only.** Quick session minting without HMAC signing.

**Request Body:**
```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "agent_id": "00000000-0000-0000-0000-0000000000a1"
}
```

**Authorization:** None (demo mode) or `Bearer <api_key>`

**Response:**
```json
{
  "status": "success",
  "session_id": "e5333b60-920b-4e30-9076-cf85ff771944",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "ttl_sec": 120,
  "ws_url": "ws://localhost:8081/ws/audio"
}
```

---

#### `POST /v1/session`
**Production** session minting with HMAC-SHA256 request signature.

**Required Headers:**
| Header | Description |
|---|---|
| `X-Tenant-Id` | Tenant UUID |
| `X-Timestamp` | Unix timestamp (seconds) |
| `X-Nonce` | Random hex string (replay protection) |
| `X-Agent-Id` | Agent UUID |
| `X-Signature` | HMAC-SHA256 of `tenant_id:timestamp:nonce:agent_id` |

**Response:** Same as `/mint`.

---

#### `POST /v1/session/refresh`
Refresh an expiring session JWT.

**Request Body:**
```json
{"token": "<current JWT>"}
```

**Response:**
```json
{"status": "success", "token": "<new JWT>", "ttl_sec": 120}
```

---

### Knowledge Bases

#### `GET /v1/knowledge-bases/status/{tenant_id}`
Returns the pgvector RAG status for a tenant.

**Path Params:** `tenant_id` — UUID

**Response:**
```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "status": "ready",
  "chunk_count": 142
}
```

---

### Usage

#### `GET /v1/usage`
Returns usage metrics for the authenticated tenant.

**Auth:** `Bearer ucve_live_<key>` (requires `tenant_viewer` role)

**Response:**
```json
{
  "tenant_id": "...",
  "session_count": 47,
  "tts_characters": 182304,
  "stt_seconds": 1420.5,
  "llm_tokens": 94200
}
```

---

### Audit Logs

#### `GET /v1/audit`
Returns compliance audit log entries for the tenant.

**Auth:** `Bearer ucve_live_<key>` (requires `audit:read` permission)

**Response:**
```json
{
  "entries": [
    {
      "event": "session_started",
      "actor": "tenant/00000000...",
      "ts": "2026-09-18T17:00:00Z"
    }
  ]
}
```

---

### Secrets

#### `POST /v1/secrets/rotate`
Rotate a provider API key for a tenant.

**Auth:** `Bearer ucve_live_<key>` (requires `secret:rotate` permission)

**Request Body:**
```json
{
  "tenant_id": "...",
  "provider_id": "elevenlabs",
  "new_secret": "sk_..."
}
```

---

### Agents

Routes under `/v1/agents/` and `/agents/` (from `control_plane/routes/agents.py`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/agents` | List agents for tenant |
| `POST` | `/agents` | Create a new agent |
| `GET` | `/agents/{agent_id}` | Get agent config |
| `PATCH` | `/agents/{agent_id}` | Update agent config |
| `DELETE` | `/agents/{agent_id}` | Delete agent |

---

### Telephony

Routes under `/v1/telephony/` (from `control_plane/routes/telephony.py`):

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/telephony/trunks` | Configure SIP trunk |
| `GET` | `/v1/telephony/trunks` | List configured trunks |
| `POST` | `/v1/telephony/inbound` | Inbound call webhook |

---

### Alerts

Routes under `/v1/alerts/` (from `control_plane/routes/alerts.py`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/alerts` | List active latency/SLA alerts |
| `POST` | `/v1/alerts` | Create alert rule |

---

### Extraction Schemas

Routes under `/v1/extraction-schemas/` (from `control_plane/routes/extraction_schemas.py`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/extraction-schemas` | List post-call extraction schemas |
| `POST` | `/v1/extraction-schemas` | Define a new extraction schema |

---

### Metrics (Prometheus)

#### `GET /metrics`
Returns Prometheus-compatible metrics in text format.

**Auth:** `Authorization: Bearer <UCVE_METRICS_BEARER>`

**Metrics exposed:**
- Session counts, turn counts
- Latency histograms (STT, LLM TTFT, TTS TTFB, E2E)
- Provider error rates

---

### Misc

| Endpoint | Description |
|---|---|
| `GET /` | Redirects to `/demo/` (developer console) |
| `GET /docs` | Swagger UI (FastAPI auto-docs) |
| `GET /favicon.ico` | Returns 204 (silences browser noise) |
| `GET /json/version` | Chrome DevTools probe handler |
| `GET /demo/` | Serves the browser demo console |

---

## Worker Node API (`worker_raw`, port 8081)

| Endpoint | Description |
|---|---|
| `GET /health` | `{"status":"ok","service":"worker-raw"}` |
| `GET /` | `{"status":"ok","ws":"/ws/audio"}` |
| `WS /ws/audio` | Real-time voice session (see WebSocket Protocol) |

---

## CORS

In development, the following origins are allowed by default:
- `http://localhost:3000`
- `http://localhost:8080`
- `http://localhost:8081`
- `http://localhost:8000`
- `http://127.0.0.1:*` variants

Override via `UCVE_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com`
