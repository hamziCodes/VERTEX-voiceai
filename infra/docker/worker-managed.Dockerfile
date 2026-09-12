# worker-managed image — optional LiveKit managed worker (Phase 28/30)
# Not required for sovereign native WS path.

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UCVE_ENV=development \
    UCVE_ENABLE_LIVEKIT=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY core/ /app/core/
COPY worker_managed/ /app/worker_managed/

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "livekit>=0.11.0" \
    "livekit-api>=0.5.0" \
    "redis>=5.0.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.9.0"

EXPOSE 8082

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

CMD ["python", "-m", "worker_managed.main"]
