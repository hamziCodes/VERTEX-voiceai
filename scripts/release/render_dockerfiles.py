"""Render every service Dockerfile in infra/docker/ from one template.

All Wavia images share one layout so the dependency layer is built once and
no image can drift from the others. Edit the template here, then run::

    python scripts/release/render_dockerfiles.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TEMPLATE = """\
# {name} image — {about}
#
# Every Wavia image has the same layout (Phase 15): third-party dependencies
# come only from requirements/runtime.txt, the hash-pinned export of uv.lock
# (regenerate with scripts/release/export_requirements.sh;
# this file is rendered by scripts/release/render_dockerfiles.py), and the image holds
# every first-party package plus the runtime assets the services read
# (scaling profiles, migrations, OpenAPI document, browser demo client).
# Build from the repository root: docker build -f infra/docker/{file} .

# Base pinned by digest (python:3.12-slim, resolved 2026-11-16); bump deliberately.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PYTHONPATH=/app \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    UCVE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends curl \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements/runtime.txt /app/requirements/runtime.txt
RUN pip install --no-deps --require-hashes -r /app/requirements/runtime.txt

{model_layer}{service_env}COPY pyproject.toml uv.lock README.md openapi.yaml /app/
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
RUN python -m core.vad.download_silero --check \\
{model_check}    && python -c "import {module}" \\
    && useradd --system --uid 10001 --home-dir /app wavia \\
    && mkdir -p /app/hamza_local \\
    && chown wavia /app/hamza_local

USER wavia

EXPOSE {port}

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \\
    CMD curl -f http://localhost:{port}/health/live || exit 1

{tail}"""

SERVICES = [
    dict(
        file="control-plane.Dockerfile",
        name="control-plane",
        about="tenant API, Studio backend and session minting (port 8080).",
        extra_env="",
        module="control_plane.app",
        port=8080,
        tail='CMD ["uvicorn", "control_plane.app:app", "--host", "0.0.0.0", "--port", "8080"]\n',
    ),
    dict(
        file="worker-raw.Dockerfile",
        name="worker-raw",
        about="native WebSocket voice worker (port 8081).",
        extra_env="ENV OMP_NUM_THREADS=1\n\n",
        module="worker_raw.main",
        port=8081,
        tail=(
            "# SIGTERM drains live sessions (WAVIA_DRAIN_TIMEOUT_S, default 120 s).\n"
            "STOPSIGNAL SIGTERM\n"
            'CMD ["python", "-m", "worker_raw.main"]\n'
        ),
    ),
    dict(
        file="telephony-gateway.Dockerfile",
        name="telephony-gateway",
        about="Telnyx webhook and media gateway (port 8083).",
        extra_env="",
        module="telephony_gateway.main",
        port=8083,
        tail='CMD ["uvicorn", "telephony_gateway.main:app", "--host", "0.0.0.0", "--port", "8083"]\n',
    ),
    dict(
        file="worker-managed.Dockerfile",
        name="worker-managed",
        about="roadmap placeholder for a managed-media worker (port 8082).\n"
        "# Its readiness always fails by design (worker_managed/main.py); the\n"
        "# sovereign native WebSocket path does not need it.",
        extra_env="",
        module="worker_managed.main",
        port=8082,
        tail='CMD ["python", "-m", "worker_managed.main"]\n',
    ),
    dict(
        file="worker-jobs.Dockerfile",
        name="worker-jobs",
        about="scheduled and queue-draining jobs runner (port 8084).",
        extra_env="",
        module="worker_jobs.main",
        port=8084,
        tail=(
            "# SIGTERM: the runner stops scheduling and lets in-flight items finish\n"
            "# (WAVIA_JOBS_DRAIN_S, default 30 s) before exiting.\n"
            "STOPSIGNAL SIGTERM\n"
            'CMD ["python", "-m", "worker_jobs.main"]\n'
        ),
    ),
]

# Knowledge embedding bundle (pinned revision + SHA-256, MIT): only the images
# that embed (control plane for preview queries, jobs runner for ingestion).
# Identical layers, so both images share one copy on disk and in a registry.
MODEL_LAYER = """\
# Pinned local embedding bundle for knowledge ingestion and retrieval.
COPY core/rag/embedders/download_model.py /tmp/wavia/download_model.py
RUN python /tmp/wavia/download_model.py --dest /opt/wavia/models/multilingual-e5-small \\
    && rm -rf /tmp/wavia
ENV UCVE_EMBEDDING_MODEL_PATH=/opt/wavia/models/multilingual-e5-small

"""
MODEL_CHECK = '    && python -m core.rag.embedders.download_model --check --dest "$UCVE_EMBEDDING_MODEL_PATH" \\\n'
EMBEDDING_IMAGES = {"control-plane", "worker-jobs"}

for service in SERVICES:
    path = ROOT / "infra" / "docker" / service["file"]
    embeds = service["name"] in EMBEDDING_IMAGES
    path.write_text(
        TEMPLATE.format(
            service_env=service["extra_env"],
            model_layer=MODEL_LAYER if embeds else "",
            model_check=MODEL_CHECK if embeds else "",
            **service,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", path.name)
