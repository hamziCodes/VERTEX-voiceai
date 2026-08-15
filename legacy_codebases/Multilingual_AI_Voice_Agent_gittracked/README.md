# 🎙️ Multilingual AI Voice Agent

A real-time, full-duplex conversational AI voice agent supporting **Arabic, Malay, English, and Urdu** — built as a commercial-grade platform for multilingual customer interaction and developer experimentation.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)
![Status](https://img.shields.io/badge/status-active--development-orange)
![License](https://img.shields.io/badge/license-Proprietary-lightgrey)
![Auth](https://img.shields.io/badge/auth-Clerk-6C47FF)
![Deploy](https://img.shields.io/badge/backend-Render-46E3B7)
![Frontend](https://img.shields.io/badge/frontend-Vercel-black)

---

## Overview

The Multilingual AI Voice Agent streams microphone audio over a persistent WebSocket, transcribes it in real-time using Gladia STT (multi-language), generates a contextual reply using Groq/Llama 3.1, synthesizes speech via Uplift AI or ElevenLabs TTS, and streams the audio back — all in a single continuous session, with full barge-in support so the user can interrupt the AI mid-sentence.

A glassmorphic developer testing dashboard (built in vanilla HTML/JS/CSS with Clerk authentication) provides a live console to monitor transcripts, latency telemetry, and the 3D audio visualizer.

> **Status:** Active Development. Core pipeline (STT → LLM → TTS), orchestration, barge-in, Clerk auth, and full deployment pipeline are implemented and verified end-to-end.

---

## Architecture

```
Browser (Microphone)
        │  PCM audio chunks (AudioWorklet → WebSocket)
        ▼
┌───────────────────────────────────────┐
│  FastAPI Backend  (Render)            │
│                                       │
│  audio_receiver.py                    │
│        │ raw PCM bytes                │
│        ▼                              │
│  gladia_service.py  ──────────────────┼──▶ Gladia Live V2 STT (WSS)
│        │ transcript (final)           │
│        ▼                              │
│  groq_service.py   ──────────────────┼──▶ Groq / Llama 3.1 (streaming)
│        │ text chunks (sentence-split) │
│        ▼                              │
│  uplift/elevenlabs_service.py ────────┼──▶ TTS Provider (streaming audio)
│        │ PCM audio frames             │
│        ▼                              │
│  audio_sender.py (→ WebSocket)        │
└───────────────────────────────────────┘
        │  PCM audio (AudioWorklet → Speaker)
        ▼
    Browser (Speaker + 3D Visualizer)
```

### Key Design Decisions
| Concern | Solution |
|---|---|
| **Barge-in** | User speech detected mid-TTS cancels generation server-side and wipes browser audio buffer instantly |
| **State machine** | Listening → Thinking → Speaking prevents double-triggers and race conditions |
| **Latency** | TTS starts before LLM finishes via sentence-boundary chunking |
| **Config safety** | `pydantic-settings` fails at startup if any required API key is missing |
| **Auth** | Clerk (hosted) — password + OTP, device verification |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, asyncio, WebSockets, uvicorn |
| STT | Gladia Live V2 |
| LLM | Groq (Llama 3.1 8B Instant) |
| TTS | Uplift AI / ElevenLabs |
| Config | pydantic-settings |
| Frontend | Vanilla HTML/JS/CSS, Web Audio API, AudioWorklet |
| Auth | Clerk |
| Containerization | Docker |
| Frontend Hosting | Vercel |
| Backend Hosting | Render (Docker Web Service) |

---

## Directory Structure

```text
Multilingual_AI_Voice_Agent/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config/
│   │   │   │   └── config.py          # pydantic-settings, fail-fast env validation
│   │   │   ├── prompts/               # LLM system prompt (retail_prompt.md)
│   │   │   └── interfaces.py          # Shared abstract interfaces / dataclasses
│   │   ├── services/
│   │   │   ├── stt/                   # gladia_service.py
│   │   │   ├── llm/                   # groq_service.py
│   │   │   └── tts/                   # uplift_service.py, elevenlabs_service.py
│   │   ├── transport/
│   │   │   ├── websocket.py           # SessionOrchestrator — main WS handler
│   │   │   ├── audio_receiver.py      # Inbound PCM consumer
│   │   │   ├── audio_sender.py        # Outbound PCM streamer
│   │   │   └── connection_manager.py  # WS lifecycle management
│   │   └── main.py                    # FastAPI app, CORS, /api/clerk-key endpoint
│   └── tests/                         # Isolated integration tests (real API calls)
├── frontend/
│   ├── index.html                     # Glassmorphic developer dashboard
│   ├── app.js                         # WebSocket engine, Clerk auth, audio pipeline
│   ├── visualizer.js                  # 3D particle wave canvas renderer
│   └── styles.css                     # Glassmorphism design system
├── docs/                              # Additional project documentation
├── .env.example                       # Template for all backend environment variables
├── .env.local.example                 # Template for Clerk keys (frontend-served)
├── Dockerfile                         # Production container for Render deployment
├── .dockerignore
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- API keys: Gladia, Groq, Uplift AI, Clerk

### 1. Clone & Install

```powershell
git clone https://github.com/hamziCodes/Multilingual_AI_Voice_Agent_gittracked.git
cd Multilingual_AI_Voice_Agent_gittracked

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the **repository root**:

```env
# .env — backend API keys
GLADIA_API_KEY=your_gladia_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MAX_HISTORY=6

UPLIFT_API_KEY=your_uplift_key
UPLIFT_VOICE_ID=your_voice_id

ELEVENLABS_API_KEY=          # optional, leave blank if using Uplift

LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000
```

Create a `.env.local` file in the **repository root** for Clerk:

```env
# .env.local — Clerk authentication keys
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

> Both files are `.gitignore`d and will never be committed. See `.env.example` and `.env.local.example` for the full template.

### 3. Run Backend

```powershell
# From repository root
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running:
- `GET http://localhost:8000/` — health check
- `GET http://localhost:8000/api/clerk-key` — Clerk key delivery to frontend
- `ws://localhost:8000/ws/audio` — live audio pipeline

### 4. Run Frontend

```powershell
cd frontend
python -m http.server 3000
```

Open `http://localhost:3000`. The dashboard auto-detects the backend. If the backend is sleeping (Render free tier), a **Wake Server** button appears — click it to initiate polling until the backend responds.

> Serving over HTTP (not `file://`) is required for Web Audio API microphone access.

---

## Live Deployment

| Service | URL |
|---|---|
| **Frontend (Vercel)** | `https://your-project.vercel.app` *(update with staging URL)* |
| **Backend (Render)** | `https://multilingual-ai-voice-agent-backend.onrender.com` |

> **Note:** Access to the live deployment is restricted via Clerk authentication. Please contact [vertex11solutions@gmail.com](mailto:vertex11solutions@gmail.com) for testing credentials.

---

## Integration Tests

Each AI service has an isolated integration test in `backend/tests/` — no mocks, real provider APIs:

```powershell
cd backend/tests
python test_gladia_pipeline.py    # STT
python test_groq_pipeline.py      # LLM (includes adversarial/jailbreak scenarios)
python test_uplift_pipeline.py    # TTS
```

---

## License

This project is proprietary software. © 2025–2026 VERTEX/studio. All Rights Reserved.
See [LICENSE](./LICENSE) for full terms.

---

## Contact

**VERTEX/studio**
[vertex11solutions@gmail.com](mailto:vertex11solutions@gmail.com)