# 08 — Universal Agent Builder & SDK Spec

File 8 of 9. Grounded primarily in `habiba-sdk-agent`, the only legacy repo with a real builder/SDK surface — its control plane, provider capability table, and browser SDK (AUDIT_04 §1: "Dynamic agent instantiation, agent configuration schemas") are the closest existing thing to what this file specifies. Extended with the domain-agnostic Agent Studio, live monitoring, and outbound-orchestrator concepts the master mandate adds on top.

---

## 1. Universal Agent Builder JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://ucve.dev/schemas/agent-config-v1.json",
  "title": "UCVE Agent Configuration",
  "type": "object",
  "required": ["agent_id", "tenant_id", "persona", "providers"],
  "properties": {
    "agent_id": { "type": "string", "format": "uuid" },
    "tenant_id": { "type": "string", "format": "uuid" },
    "persona": {
      "type": "object",
      "required": ["system_prompt", "greeting"],
      "properties": {
        "system_prompt": { "type": "string", "description": "Framed as DATA per File 6 §1, never concatenated into core SYSTEM_INSTRUCTIONS" },
        "greeting": { "type": "string" },
        "voice_id": { "type": "string" },
        "persona_isolation": { "type": "boolean", "default": true, "description": "habiba pattern, AUDIT_04 §1 — kept true by default" }
      }
    },
    "languages": {
      "type": "array",
      "items": { "$ref": "#/$defs/languageProfile" }
    },
    "providers": { "$ref": "#/$defs/providerConfig" },
    "tools": {
      "type": "array",
      "items": { "$ref": "#/$defs/toolConfig" }
    },
    "mcp_servers": {
      "type": "array",
      "items": { "$ref": "#/$defs/mcpServerConfig" }
    },
    "knowledge_bases": {
      "type": "array",
      "items": { "$ref": "#/$defs/knowledgeBaseSource" }
    },
    "extraction_schema_id": { "type": "string", "description": "File 5 §3 TenantExtractionSchema reference" },
    "disposition_enum_ref": { "type": "string", "description": "Optional override; default dispositions in File 5 §5 CallDisposition" },
    "pronunciation_lexicon": {
      "type": "array",
      "description": "File 4 §3.1 step 3 — tenant phonetic overrides for brand/SKU terms",
      "items": {
        "type": "object",
        "required": ["grapheme", "phoneme"],
        "properties": {
          "grapheme": { "type": "string" },
          "phoneme": { "type": "string" },
          "language": { "type": "string" }
        }
      }
    },
    "telephony": { "$ref": "#/$defs/telephonyConfig" },
    "compliance": { "$ref": "#/$defs/redactionPolicyRef" }
  },
  "$defs": {
    "languageProfile": {
      "type": "object",
      "properties": {
        "code": { "type": "string" },
        "vad_silence_override_ms": { "type": "integer" },
        "tts_voice_id": { "type": "string" },
        "code_switching": { "type": "boolean", "default": false, "description": "File 4 §1: default false per habiba's measured CER rationale, overridable per tenant" }
      }
    },
    "providerConfig": {
      "type": "object",
      "properties": {
        "stt": { "type": "object", "additionalProperties": { "type": "array", "items": { "type": "string" } } },
        "llm": { "type": "object", "additionalProperties": { "type": "array", "items": { "type": "string" } } },
        "tts": { "type": "object", "additionalProperties": { "type": "array", "items": { "type": "string" } } },
        "s2s": { "type": "object", "properties": { "enabled": { "type": "boolean", "default": false } } }
      },
      "description": "See File 3 §5.2 for the priority-chain config shape this mirrors"
    },
    "toolConfig": {
      "type": "object",
      "required": ["name", "description", "parameters_schema"],
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "parameters_schema": { "type": "object" }
      }
    },
    "mcpServerConfig": {
      "type": "object",
      "required": ["server_id", "transport"],
      "properties": {
        "server_id": { "type": "string" },
        "transport": { "enum": ["stdio", "sse", "streamable_http"] },
        "endpoint": { "type": "string" },
        "allowed_tools": { "type": "array", "items": { "type": "string" } }
      }
    },
    "knowledgeBaseSource": {
      "type": "object",
      "properties": {
        "source_type": { "enum": ["pdf_upload", "faq_list", "web_scrape", "manual_entry"] },
        "source_uri": { "type": "string" },
        "refresh_interval_hours": { "type": "integer" }
      }
    },
    "telephonyConfig": {
      "type": "object",
      "properties": {
        "inbound_dids": { "type": "array", "items": { "type": "string" } },
        "outbound_enabled": { "type": "boolean", "default": false },
        "calling_window": { "type": "object", "description": "File 7 §4.2 CallingWindow" }
      }
    },
    "redactionPolicyRef": {
      "type": "object",
      "properties": {
        "compliance_tier": { "enum": ["standard", "hipaa", "gdpr", "pci_dss"] },
        "policy_id": { "type": "string" }
      }
    }
  }
}
```

**Provenance mapping:**

| Schema section | Legacy source pattern | Citation |
|---|---|---|
| `persona.persona_isolation` | habiba's separate `chat_ctx` frame | AUDIT_04 §1 |
| `providers` shape | habiba `capabilities.py` (language, provider_type) → status | AUDIT_04 §2 |
| `tools` / `mcp_servers` | habiba `FIXED_TOOLS` generalized to MCP (File 6 §2) | AUDIT_04 §2 LLM |
| `languages[].code_switching` | File 4 §1 measured CER decision | AUDIT_04 §2 VAD/STT |
| `knowledge_bases` | `[NEW]` — awaazlabs' dashboard `knowledge` UI folder exists but has no live ingestion pipeline behind it (AUDIT_02 §6: "UI surface") — this schema section is the actual pipeline that folder implies but doesn't implement |
| `telephony` | habiba's Telnyx DID/webhook pattern generalized | AUDIT_04 §4 |

---

## 2. OpenAPI 3.1 — Control Plane Surface

Generalizes habiba's control plane endpoints (AUDIT_04 §4) to the domain-agnostic platform. Endpoint shapes below are habiba's actual routes, kept intact where they're already good design, with additions flagged `[NEW]`.

```yaml
openapi: 3.1.0
info:
  title: UCVE Control Plane API
  version: 1.0.0
paths:
  /v1/session:
    post:
      summary: Mint a session token (habiba pattern, AUDIT_04 §4)
      security: [{ hmacAuth: [] }]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [agent_id]
              properties:
                agent_id: { type: string, format: uuid }
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  token: { type: string }
                  wsUrl: { type: string }
                  roomName: { type: string }
                  refreshUrl: { type: string }
                  expiresIn: { type: integer, example: 120 }
  /v1/session/refresh:
    post:
      summary: Refresh a near-expiry JWT (habiba pattern — 120s TTL, AUDIT_04 §3)
      security: [{ bearerAuth: [] }]
      responses:
        "200": { description: New 120s JWT issued }
  /v1/voices:
    get:
      summary: Voice catalogue (habiba pattern; note the fail-open bug to FIX not inherit)
      description: >
        habiba's implementation swallows DB errors and silently returns a
        demo catalogue (AUDIT_04 §6: "/v1/voices swallows DB errors and
        returns demo catalogue"). UCVE's equivalent endpoint must surface
        the error state explicitly (e.g. a `degraded: true` flag) rather
        than silently serving fallback data indistinguishable from real data.
      responses:
        "200": { description: List of available voices per provider capability table }
  /v1/agents:
    post:
      summary: "[NEW] Create/update an agent via the builder schema (§1 above)"
      security: [{ tenantJWT: [] }]
  /v1/knowledge-bases:
    post:
      summary: "[NEW] Ingest a knowledge base source (File 6 §3 RAGRetriever backing store)"
      security: [{ tenantJWT: [] }]
  /v1/extraction-schemas:
    post:
      summary: "[NEW] Register a TenantExtractionSchema (File 5 §3)"
      security: [{ tenantJWT: [] }]
  /v1/webhooks:
    post:
      summary: "[NEW] Register a WebhookTarget for post-call CRM dispatch (File 5 §6)"
      security: [{ tenantJWT: [] }]
  /v1/campaigns:
    post:
      summary: "[NEW] Create an outbound campaign (File 7 §4.2)"
      security: [{ tenantJWT: [] }]
  /healthz:
    get:
      summary: Basic liveness (all four legacy repos have some form of this)
      responses:
        "200": { description: OK }
  /healthz/deep:
    get:
      summary: "DB + media-plane readiness (habiba pattern, AUDIT_04 §4)"
components:
  securitySchemes:
    hmacAuth:
      type: apiKey
      in: header
      name: X-Signature
      description: "HMAC(tenant_id.ts.nonce.agent_id), 60s replay window — habiba pattern, AUDIT_04 §3 handshake"
    bearerAuth: { type: http, scheme: bearer }
    tenantJWT: { type: http, scheme: bearer }
```

---

## 3. WebSocket / Realtime Event Protocol

Unifies three previously-divergent event vocabularies found across the audits — v3/multilingual's raw-WS control events and habiba's LiveKit SDK events used *different names for the same concepts*, which is exactly the kind of fragmentation the transport gateway (File 1 §3.4) exists to eliminate:

| Concept | v3 event name | Multilingual event name | Habiba SDK event name | **UCVE unified name** |
|---|---|---|---|---|
| Transcript update | `transcript` | `transcript` | `transcript` | `transcript` |
| Barge-in occurred | `control`/`barge_in` | `control`/`barge_in` | (implicit, LiveKit-native) | `control.barge_in` |
| Call ended | `ws.close(1000)` | `control`/`hangup` | `disconnected`/`ended` | `control.hangup` |
| Latency metric | `metric` | `metric` | `metrics_updated` | `metric` |
| Error | `error` | `error` | `error` | `error` |
| Heartbeat | `ping` | `control`/`ping` | (LiveKit-native, not exposed) | `control.ping` |
| Speaking indicator | (absent) | (absent) | `speaking`/`agent_speaking` | `control.speaking_state` |

Citations: v3 AUDIT_01 §4 WS catalog; multilingual AUDIT_03 §4 WS catalog; habiba AUDIT_04 §4 SDK event table.

```typescript
// Server→client (and shared) events. STT model type is File 3 `Transcript`
// (text/is_final/language/confidence). This wire event adds `speaker` for
// UI/diarization and uses camelCase; post-call turns are File 5 `DiarizedTurn`.
export type UCVERealtimeEvent =
  | { type: "transcript"; speaker: "agent" | "user"; text: string; isFinal: boolean; language?: string; confidence?: number }
  | { type: "control.barge_in" }
  | { type: "control.hangup"; reason: string }
  | { type: "control.ping" }
  | { type: "control.pong" }                 // client→server keepalive reply (File 7 §3.2)
  | { type: "control.speaking_state"; speaker: "agent" | "user"; active: boolean }
  | { type: "metric"; name: string; value: number; highlight?: boolean }
  | { type: "error"; message: string; code?: string }
  | { type: "tool.filler_started" }      // File 6 §2.3
  | { type: "tool.call"; name: string; arguments: Record<string, unknown> }
  | { type: "client.interrupt_hint" };   // client→server explicit stop-talking

export type UCVEClientToServerEvent =
  | { type: "control.pong" }
  | { type: "client.interrupt_hint" };
```

**Client→server events:** all four legacy repos are asymmetric — client sends raw binary audio only, zero JSON events upstream except LiveKit's implicit media-track state (v3: AUDIT_01 §4 "Client→server is raw binary only"; multilingual: AUDIT_03 §4 "Client→server JSON events: NOT IMPLEMENTED / ABSENT"; habiba: "Client→server custom JSON events: NOT IMPLEMENTED / ABSENT" since media goes via WebRTC, AUDIT_04 §4). UCVE keeps this asymmetry deliberately for media — it's a consistent, evidenced design choice across all three real-time-capable repos, not an oversight — but adds an explicit client→server control channel for the raw plane's `control.pong` response (File 7 §3.2 gap fix) and an optional `client.interrupt_hint` event for clients that want to signal an explicit "stop talking" button press rather than relying solely on VAD-detected barge-in.

> Corrected during finalization pass: client→server event types are now named in the TypeScript unions above (previously only described in prose).

---

## 4. Client SDK Interfaces

### 4.1 Python

```python
class UCVEVoiceClient:
    """Mirrors habiba's @awaazlabs-uva/voice zero-secret pattern
    (AUDIT_04 §2 transport) — the SDK never holds provider API keys,
    only a publishableKey + agentId, exchanged for a session token via
    the tenant's own host backend (not directly to UCVE control plane)."""

    def __init__(self, publishable_key: str, agent_id: str, session_endpoint: str): ...

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...

    def on(self, event: str, handler: "Callable[[UCVERealtimeEvent], None]") -> None: ...
    async def send_interrupt_hint(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...
```

### 4.2 TypeScript / React

```typescript
export interface UCVEVoiceClientOptions {
  publishableKey: string;
  agentId: string;
  sessionEndpoint: string;
}

export class UCVEVoiceClient {
  constructor(options: UCVEVoiceClientOptions);
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  on(event: string, handler: (e: UCVERealtimeEvent) => void): void;
  sendInterruptHint(): Promise<void>;
  readonly isConnected: boolean;
}

// React hook wrapper, following habiba SDK's ergonomics (AUDIT_04 §2 transport)
export function useUCVEVoice(options: UCVEVoiceClientOptions): {
  client: UCVEVoiceClient;
  transcript: string;
  isAgentSpeaking: boolean;
  isConnected: boolean;
};
```

### 4.3 Flutter/Dart

```dart
class UCVEVoiceClient {
  UCVEVoiceClient({
    required String publishableKey,
    required String agentId,
    required String sessionEndpoint,
  });

  Future<void> connect();
  Future<void> disconnect();
  void on(String event, void Function(Map<String, dynamic>) handler);
  Future<void> sendInterruptHint();
  bool get isConnected;
}
```

---

## 5. Agent Studio UI — Feature Set (spec, not implementation)

Not code — a checklist of what the builder UI must expose, mapped to the schema in §1:

- Persona editor: system prompt (with a visible "this is tenant data, isolated from core instructions" indicator — surfacing File 6 §1's security model to the tenant builder, not just enforcing it silently)
- Voice/persona picker per language, with live TTS preview
- Provider priority drag-and-drop per capability (STT/LLM/TTS), rendered from the `ProviderCapabilityEntry` table (File 3 §3 TS types)
- Tool/MCP server connection manager
- Knowledge base upload (PDF/FAQ/web-scrape) with ingestion status
- Extraction schema builder (visual form-builder over `TenantExtractionSchema`, File 5 §3)
- Telephony DID assignment + calling-window compliance editor (File 7 §4.2)
- Live call monitor panel (File 7 §5) with whisper control
- Outbound campaign builder with AMD/voicemail-drop toggles
