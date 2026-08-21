# worker-raw image — builds from underscore package dir worker_raw/

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UCVE_ENV=development \
    OMP_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY core/pyproject.toml /app/core/pyproject.toml
COPY core/ /app/core/
COPY control_plane/ /app/control_plane/
COPY worker_raw/pyproject.toml /app/worker_raw/pyproject.toml
COPY worker_raw/ /app/worker_raw/

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "websockets>=13.0" \
    "httpx>=0.27.0" \
    "redis>=5.0.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.9.0" \
    "cryptography>=43.0.0" \
    "PyJWT>=2.9.0" \
    "PyYAML>=6.0.2" \
    "numpy>=2.0.0" \
    "onnxruntime>=1.19.0"

EXPOSE 8081

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

CMD ["python", "-m", "worker_raw.main"]
