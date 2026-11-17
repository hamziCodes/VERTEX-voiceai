# worker-jobs image — scheduled and queue-draining jobs runner (port 8084).
#
# Every Wavia image has the same layout (Phase 15): third-party dependencies
# come only from requirements/runtime.txt, the hash-pinned export of uv.lock
# (regenerate with scripts/release/export_requirements.sh;
# this file is rendered by scripts/release/render_dockerfiles.py), and the image holds
# every first-party package plus the runtime assets the services read
# (scaling profiles, migrations, OpenAPI document, browser demo client).
# Build from the repository root: docker build -f infra/docker/worker-jobs.Dockerfile .

# Base pinned by digest (python:3.12-slim, resolved 2026-11-16); bump deliberately.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UCVE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/runtime.txt /app/requirements/runtime.txt
RUN pip install --no-deps --require-hashes -r /app/requirements/runtime.txt

# Pinned local embedding bundle for knowledge ingestion and retrieval.
COPY core/rag/embedders/download_model.py /tmp/wavia/download_model.py
RUN python /tmp/wavia/download_model.py --dest /opt/wavia/models/multilingual-e5-small \
    && chmod -R a+rX /opt/wavia \
    && rm -rf /tmp/wavia
ENV UCVE_EMBEDDING_MODEL_PATH=/opt/wavia/models/multilingual-e5-small

COPY pyproject.toml uv.lock README.md openapi.yaml /app/
COPY core/ /app/core/
COPY control_plane/ /app/control_plane/
COPY post_call/ /app/post_call/
COPY telephony_gateway/ /app/telephony_gateway/
COPY worker_raw/ /app/worker_raw/
COPY worker_jobs/ /app/worker_jobs/
COPY worker_managed/ /app/worker_managed/
COPY infra/__init__.py /app/infra/__init__.py
COPY infra/scaling/ /app/infra/scaling/
COPY infra/db/ /app/infra/db/
COPY examples/web-client/ /app/examples/web-client/

# The Silero VAD model ships in the repository; refuse to build an image whose
# copy is not the pinned release.
RUN python -m core.vad.download_silero --check \
    && python -c "import worker_jobs.main" \
    && useradd --system --uid 10001 --home-dir /app wavia \
    && mkdir -p /app/hamza_local \
    && chown wavia /app/hamza_local

USER wavia
RUN python -m core.rag.embedders.download_model --check --dest "$UCVE_EMBEDDING_MODEL_PATH"

EXPOSE 8084

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8084/health/live || exit 1

# SIGTERM: the runner stops scheduling and lets in-flight items finish
# (WAVIA_JOBS_DRAIN_S, default 30 s) before exiting.
STOPSIGNAL SIGTERM
CMD ["python", "-m", "worker_jobs.main"]
