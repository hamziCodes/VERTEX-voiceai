# control-plane: API + mint + OpenAPI docs (Phase 30 stub)

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY control-plane/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir fastapi uvicorn

COPY control-plane/ /app/control-plane/

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "control_plane.app:app", "--host", "0.0.0.0", "--port", "8080"]
