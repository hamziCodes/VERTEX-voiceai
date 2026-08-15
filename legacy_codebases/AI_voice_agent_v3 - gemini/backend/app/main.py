import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# 1. Add the project root to the Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 2. Aggressively load and validate settings BEFORE anything else
from backend.app.core.config.config import get_settings
try:
    settings = get_settings()
except Exception as exc:
    logging.basicConfig(level="INFO")
    logging.getLogger(__name__).critical("🚨 CRITICAL: Startup aborted — invalid/missing .env config: %s", exc)
    sys.exit(1)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 3. NOW it is safe to import our services
from backend.app.transport.websocket import router as transport_router

# Configure logging: console (short) + logs/app.log (full) + logs/vad_frames.log (isolated)
from backend.app.core.logging_config import setup_logging
setup_logging(console_level=settings.log_level)
logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Verifying Silero VAD status...")
    from backend.app.services.silero_service import check_silero_status
    if check_silero_status():
        logger.info("✅ Silero VAD status: ACTIVE and running.")
    else:
        logger.error("🚨 CRITICAL ERROR: Silero VAD is NOT active or failed to load. The voice agent pipeline will reject connections.")

    logger.info("\n--- Urdu Voice Agent Backend ---")
    logger.info("Successfully started on http://localhost:8000")
    logger.info("WebSocket connections available at ws://localhost:8000/ws/audio")
    logger.info("---------------------------------\n")
    yield
    logger.info("--- Shutting down server ---")

app = FastAPI(title="Urdu Voice Agent Platform backend", version="1.0.0", lifespan=lifespan)

# Allow the frontend HTML file to connect using config origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include websocket routes we built in transport layer in websocket.py
app.include_router(transport_router)

@app.get("/")
async def root_check():
    return {"Status": "online", "message": "Urdu Voice Agent Core Ingestion Layer Operational"}

@app.get("/healthz")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # Start the asynchronous ASGI web server on port 8000
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True, log_level=settings.log_level.lower())