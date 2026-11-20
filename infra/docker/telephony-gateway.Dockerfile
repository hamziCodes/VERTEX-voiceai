# telephony-gateway image — Telnyx webhook and media gateway (port 8083).
#
# Every Wavia image has the same layout (Phase 15): third-party dependencies
# come only from requirements/runtime.txt, the hash-pinned export of uv.lock
# (regenerate with scripts/release/export_requirements.sh;
# this file is rendered by scripts/release/render_dockerfiles.py), and the image holds
# every first-party package plus the runtime assets the services read
# (scaling profiles, migrations, OpenAPI document, browser demo client).
# Build from the repository root: docker build -f infra/docker/telephony-gateway.Dockerfile .

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
    && python -c "import telephony_gateway.main" \
    && useradd --system --uid 10001 --home-dir /app wavia \
    && mkdir -p /app/hamza_local \
    && chown wavia /app/hamza_local

USER wavia

EXPOSE 8083

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8083/health/live || exit 1

CMD ["uvicorn", "telephony_gateway.main:app", "--host", "0.0.0.0", "--port", "8083"]
