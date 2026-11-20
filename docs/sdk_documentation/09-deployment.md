# Deployment Guide

---

## Local Development (Direct Python / Uvicorn)

No virtual environment is required when `pip install -e .` has been run from the repo root.

### Control Plane
```bash
python -m uvicorn control_plane.app:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

### Worker Raw Node
```bash
python -m uvicorn worker_raw.main:app \
  --host 127.0.0.1 \
  --port 8081 \
  --reload
```

### Telephony Gateway (optional)
```bash
python -m uvicorn telephony_gateway.main:app \
  --host 127.0.0.1 \
  --port 8082
```

---

## Environment Checklist

Before starting any service, ensure these are set in `.env`:

```env
# Minimum for local demo
GLADIA_API_KEY=...
GROQ_API_KEY=...
UPLIFT_API_KEY=...
UCVE_MINT_HMAC_SECRET=dev-mint-secret
UCVE_ENV=development
```

The system will raise an error on startup if required production secrets are missing (checked via `require_production_secrets()`).

---

## Production Deployment

### Service Ports

| Service | Port | Notes |
|---|---|---|
| `control_plane` | `8000` | Expose behind TLS termination proxy |
| `worker_raw` | `8081` | WebSocket — must support HTTP upgrade |
| `telephony_gateway` | `8082` | Needs public URL for Telnyx webhooks |

### Recommended Stack

```
Internet → Nginx / Caddy (TLS + WebSocket proxy)
    ├── → control_plane:8000
    └── → worker_raw:8081 (WebSocket: /ws/audio)
```

### Uvicorn Production Settings

```bash
# Control Plane
python -m uvicorn control_plane.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log

# Worker Raw
python -m uvicorn worker_raw.main:app \
  --host 0.0.0.0 \
  --port 8081 \
  --workers 2 \
  --no-access-log
```

> The worker node is stateful per-connection — do **not** use more workers than expected concurrent sessions per machine.

---

## Docker (Reference)

The services are each independently containerizable. A minimal example:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .
ENV UCVE_ENV=production
CMD ["python", "-m", "uvicorn", "control_plane.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Infrastructure Dependencies

| Dependency | Required? | Usage |
|---|---|---|
| PostgreSQL + pgvector | Optional* | Session storage, RAG knowledge bases, audit logs |
| Redis | Optional* | Session JWT cache, distributed state |
| Gladia account | Recommended | Default STT provider |
| Groq account | Recommended | Default LLM provider |
| Uplift account | Recommended | Default TTS provider |

> *In development mode, in-memory stubs replace DB/Redis dependencies.

---

## CI/CD — GitHub Actions

Two workflows in `.github/workflows/`:

### `ci.yml` — Continuous Integration
Runs on every push and pull request to `main`:
1. `pip install -e .` with all optional deps
2. `ruff check .` — linting
3. `mypy core/` — type checking
4. `pytest tests/ voice_engine_plan/tests/` — 407 tests
5. Pytest mode: `asyncio_mode = strict`

### `security-audit.yml` — Security Scan
1. `pip-audit` — dependency vulnerability scan
2. Secret scanning via `trufflesecurity/trufflehog`

---

## Running Tests

```bash
# Full test suite
pytest

# Specific module
pytest tests/unit/test_fsm.py -v

# With coverage
pytest --cov=core --cov-report=term-missing

# Skip slow integration tests
pytest -m "not integration"
```

Test paths: `tests/` and `voice_engine_plan/tests/`  
Pytest asyncio mode: `strict` (all async tests must be decorated with `@pytest.mark.asyncio`)

---

## Scaling Considerations

| Concern | Guidance |
|---|---|
| Concurrent sessions | Each WS connection holds one `PipelineOrchestrator` — memory ~50MB/session |
| TTS latency | Uplift returns 16 kHz natively — no resampling overhead |
| RAG | pgvector HNSW index recommended for >10k chunks |
| Barge-in | Flush latency is <5ms (in-memory queue drain) |
| STT streaming | One Gladia Live WS per session — Gladia concurrent connection limits apply |
