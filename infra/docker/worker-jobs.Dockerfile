# worker-jobs image — the scheduled/queue-draining jobs runner (Phase 14).
# Installs runtime dependencies from the root pyproject so the image matches
# the locked application, then runs `python -m worker_jobs.main` on 8084.

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UCVE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY core/ /app/core/
COPY control_plane/ /app/control_plane/
COPY post_call/ /app/post_call/
COPY worker_jobs/ /app/worker_jobs/
COPY worker_raw/ /app/worker_raw/
COPY telephony_gateway/ /app/telephony_gateway/
COPY infra/__init__.py /app/infra/__init__.py
COPY infra/scaling/ /app/infra/scaling/

RUN pip install --no-cache-dir ".[knowledge-s3]"

EXPOSE 8084

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8084/health/live || exit 1

# SIGTERM: the runner stops scheduling and lets in-flight items finish
# (WAVIA_JOBS_DRAIN_S, default 30 s) before exiting.
STOPSIGNAL SIGTERM
CMD ["python", "-m", "worker_jobs.main"]
