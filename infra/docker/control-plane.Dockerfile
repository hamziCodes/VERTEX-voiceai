# control-plane image — builds from underscore package dir control_plane/

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UCVE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY core/pyproject.toml /app/core/pyproject.toml
COPY core/ /app/core/
COPY post_call/ /app/post_call/
COPY control_plane/pyproject.toml /app/control_plane/pyproject.toml
COPY control_plane/ /app/control_plane/

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "httpx>=0.27.0" \
    "PyJWT>=2.9.0" \
    "redis>=5.0.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.9.0" \
    "cryptography>=43.0.0" \
    "PyYAML>=6.0.2" \
    "websockets>=13.0" \
    "numpy>=2.0.0"

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health/live || exit 1

CMD ["uvicorn", "control_plane.app:app", "--host", "0.0.0.0", "--port", "8080"]
