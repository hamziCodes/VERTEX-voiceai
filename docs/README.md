# Wavia SDK — Developer Documentation

> **Production-grade, sovereign real-time voice AI engine.**

---

## Documentation Index

| # | Title | Description |
|---|---|---|
| [01](./01-overview.md) | **Overview** | Architecture, service map, technology stack, provider matrix |
| [02](./02-quickstart.md) | **Quickstart** | Get running locally in 5 minutes |
| [03](./03-session-lifecycle.md) | **Session Lifecycle** | FSM states, events, turn flow, barge-in, teardown |
| [04](./04-websocket-protocol.md) | **WebSocket Protocol** | Audio format, control events, close codes |
| [05](./05-providers.md) | **Provider Reference** | STT/LLM/TTS providers, interfaces, custom providers |
| [06](./06-api-reference.md) | **API Reference** | All REST endpoints, auth, CORS |
| [07](./07-configuration.md) | **Configuration** | All environment variables and feature flags |
| [08](./08-core-modules.md) | **Core Modules** | Internal library reference (buffers, FSM, RAG, compliance) |
| [09](./09-deployment.md) | **Deployment** | Local, production, Docker, CI/CD, scaling |
| [10](./10-troubleshooting-and-errors.md) | **Troubleshooting** | Common errors, audio issues, error code reference |

---

## Quick Reference

### Local Dev Commands
```bash
# Control Plane
python -m uvicorn control_plane.app:app --host 127.0.0.1 --port 8000 --reload

# Worker Raw Node
python -m uvicorn worker_raw.main:app --host 127.0.0.1 --port 8081 --reload

# Tests
pytest

# Lint
ruff check .
```

### Service Ports
| Service | URL |
|---|---|
| Control Plane | `http://127.0.0.1:8000` |
| Worker Raw | `http://127.0.0.1:8081` |
| Demo Console | `http://127.0.0.1:8000/demo/` |
| API Docs | `http://127.0.0.1:8000/docs` |
