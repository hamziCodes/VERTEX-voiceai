# worker-raw: sovereign pipeline worker (Phase 30)
# Explicit torch/numpy — fixes multilingual undeclared-deps gap (File 9 §4.1)

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY worker-raw/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir torch numpy

COPY worker-raw/ /app/worker-raw/
COPY core/ /app/core/

EXPOSE 8081

CMD ["python", "-m", "worker_raw.main"]
