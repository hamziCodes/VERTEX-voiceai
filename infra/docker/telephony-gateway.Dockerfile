# telephony-gateway image — SIP / PSTN inbound gateway (Phase 18/19/30)

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UCVE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY core/ /app/core/
COPY telephony_gateway/ /app/telephony_gateway/

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "httpx>=0.27.0" \
    "redis>=5.0.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.9.0" \
    "cryptography>=43.0.0" \
    "numpy>=2.0.0"

EXPOSE 8083

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8083/health/live || exit 1

CMD ["uvicorn", "telephony_gateway.main:app", "--host", "0.0.0.0", "--port", "8083"]
