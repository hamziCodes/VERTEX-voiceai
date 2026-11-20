# Overview

## What is Wavia?

**Wavia** (codename: UCVE — Unified Conversational Voice Engine) is a **sovereign, self-hosted real-time voice AI engine** designed for production-grade conversational agents. It provides a fully orchestrated Speech-to-Text → LLM → Text-to-Speech pipeline over a persistent WebSocket connection, with sub-500ms end-to-end latency targets.

Wavia is:
- **Provider-agnostic** — swap STT, LLM, and TTS vendors per session
- **Compliance-ready** — HIPAA/GDPR redaction tiers built in
- **Self-hosted sovereign** — no cloud vendor lock-in for the core runtime
- **Multi-tenant** — tenant-scoped sessions, knowledge bases, and secrets

---

## System Architecture

Wavia is structured as a **Python monorepo** managed by Hatchling and uv. It consists of five independently deployable micro-services, plus a shared `core` library.

```
VERTEX_voiceai/
├── core/                  # Shared library — providers, FSM, buffers, RAG, compliance
├── control_plane/         # FastAPI REST: session minting, tenant management, RBAC
├── worker_raw/            # FastAPI + WebSocket: real-time audio pipeline node
├── telephony_gateway/     # SIP/PSTN telephony adapter (Telnyx)
├── post_call/             # Async post-call summarization, extraction, scoring
├── sdk/                   # Client SDKs — Python, TypeScript, Flutter
└── examples/web-client/   # Browser demo console (served at /demo)
```

---

## Service Responsibilities

| Service | Port | Protocol | Responsibility |
|---|---|---|---|
| `control_plane` | `8000` | HTTP/REST | JWT session minting, agent config, knowledge bases, RBAC |
| `worker_raw` | `8081` | HTTP + WebSocket | Real-time audio ingress, VAD, STT/LLM/TTS orchestration |
| `telephony_gateway` | — | SIP/Webhook | Inbound/outbound PSTN call routing via Telnyx |
| `post_call` | — | Internal | Async transcript summarization, data extraction, scoring |
| `core` | N/A | Library | All shared domain logic (providers, FSM, compliance, RAG) |

---

## Real-Time Pipeline Flow

A single conversation turn follows this flow:

```
Browser/Client
    │
    ├─ [POST /mint] ──────────────────────► Control Plane (8000)
    │                                            │ JWT session token
    │◄────────────────────────────────────────────┘
    │
    ├─ [WS /ws/audio?token=...] ──────────► Worker Raw (8081)
    │                                            │
    │  Raw PCM16 audio frames ──────────────►    │
    │                                        Frame Slicer
    │                                            │
    │                                        Silero VAD
    │                                      (speech detection)
    │                                            │ speech_end
    │                                        Gladia STT
    │                                      (transcription)
    │                                            │ text
    │                                        RAG Retrieval
    │                                      (pgvector context)
    │                                            │
    │                                        LLM Stream
    │                                      (Groq / Gemini / OpenAI)
    │                                            │ tokens
    │                                        Sentence Chunker
    │                                            │
    │                                        TTS Stream
    │                                      (Uplift / ElevenLabs / Cartesia)
    │                                            │ PCM16 audio
    │◄─────────────────── binary WS frames ───────┘
```

---

## Key Design Decisions

### 1. WebSocket-First Audio Transport
All real-time audio flows over a persistent WebSocket (`/ws/audio`). The client sends raw **16-bit PCM audio frames** (16 kHz, mono) as binary WebSocket messages. The server responds with binary PCM frames and JSON control events.

### 2. Session FSM
Every session is governed by a deterministic **state machine** (`SessionFSM`) with 9 named states:

```
CONNECTING → LISTENING → USER_SPEAKING → PROCESSING_INFERENCE
                                                ↓
                                         TOOL_EXECUTING
                                                ↓
                               AGENT_SPEAKING → BARGE_IN_VERIFY
                                                ↓
                                      BARGE_IN_INTERRUPTED
```

### 3. Provider Abstraction
STT, LLM, and TTS are plug-and-play adapters behind abstract base classes. Providers are registered in `ProviderRegistry` and selected per-session at WebSocket connect time via query parameters.

### 4. Barge-In Support
While the agent is speaking (`AGENT_SPEAKING`), incoming VAD speech onset immediately cancels the LLM/TTS tasks via `AsyncioCancellationToken`, flushes the egress queue, and reactivates the listening pipeline — all within ~100ms.

### 5. Tenant Isolation
All sessions are scoped to a `tenant_id` + `agent_id`. Knowledge bases, secrets, compliance profiles, and audit logs are stored and enforced per-tenant.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+ |
| Web Framework | FastAPI + Uvicorn |
| WebSocket | Starlette native WebSocket |
| Audio Processing | NumPy, ONNX Runtime (Silero VAD) |
| Database | PostgreSQL + pgvector (RAG) |
| Cache / Session | Redis |
| Authentication | PyJWT (HS256) |
| Build System | Hatchling + uv |
| Linting | Ruff |
| Type Checking | Mypy |
| Testing | pytest + pytest-asyncio |

---

## Supported Providers

### Speech-to-Text (STT)
| Provider ID | Class | Mode |
|---|---|---|
| `gladia` | `GladiaSTTProvider` | Batch |
| `gladia_live` | `GladiaLiveSTTSession` | Streaming WebSocket |
| `deepgram` | `DeepgramSTTProvider` | Batch |
| `null` | `NullSTTProvider` | Testing |

### Large Language Model (LLM)
| Provider ID | Class | Notes |
|---|---|---|
| `groq` | `GroqLLMProvider` | Default; ultra-low latency |
| `gemini` | `GeminiLLMProvider` | Google Gemini 2.5 Flash |
| `openai` | `OpenAILLMProvider` | GPT-4o-mini / GPT OSS |
| `null` | `NullLLMProvider` | Testing |

### Text-to-Speech (TTS)
| Provider ID | Class | Notes |
|---|---|---|
| `uplift` | `UpliftTTSProvider` | Default |
| `elevenlabs` | `ElevenLabsTTSProvider` | High-quality voices |
| `cartesia` | `CartesiaTTSProvider` | Low-latency streaming |
| `null` | `NullTTSProvider` | Testing |
