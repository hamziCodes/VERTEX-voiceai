# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required by pydub/ffmpeg_downloader
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Set PYTHONPATH so that "backend.app.main" resolves correctly from /app
ENV PYTHONPATH=/app

# Expose the port uvicorn listens on
EXPOSE 8000

# Start uvicorn — must bind 0.0.0.0 for container hosts to route traffic
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
