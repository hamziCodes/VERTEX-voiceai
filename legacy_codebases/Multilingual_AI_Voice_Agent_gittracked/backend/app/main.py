import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

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

from backend.app.transport.websocket import router as transport_router

# Define Console Filter to omit conversational/recurring noise logs from the terminal
class ConsoleLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        verbose_loggers = (
            "backend.app.services.vad.vad_service",
            "backend.app.services.stt.gladia_service",
            "backend.app.services.llm.groq_service",
            "backend.app.services.tts.tts_manager",
            "backend.app.transport.audio_sender",
            "backend.app.transport.audio_receiver",
            "backend.app.transport.connection_manager",
            "backend.app.orchestration.session",
        )
        # Discard INFO/DEBUG logs from verbose session engines to keep terminal clean
        if record.name in verbose_loggers or any(record.name.startswith(l + ".") for l in verbose_loggers):
            return record.levelno >= logging.WARNING
        return True

# Setup directory and handlers
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

app_log_file = log_dir / "app.log"
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# File Handler (all logs)
app_handler = RotatingFileHandler(app_log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
app_handler.setLevel(settings.log_level)
app_handler.setFormatter(formatter)

# Console Handler (filtered logs only)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(settings.log_level)
console_formatter = logging.Formatter("%(levelname)s:     %(message)s")
console_handler.setFormatter(console_formatter)
console_handler.addFilter(ConsoleLogFilter())

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(settings.log_level)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
root_logger.addHandler(app_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger("uvicorn.error")

async def check_silero_status() -> None:
    """Performs a dry-run inference on Silero VAD at startup to set its health state."""
    from backend.app.services.vad.health import set_silero_healthy
    logger.info("[Startup] Performing Silero VAD model health check...")
    try:
        import torch
        from backend.app.services.vad.vad_service import configure_torch_threads
        configure_torch_threads()
        
        model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        
        from backend.app.services.vad.vad_service import find_silero_jit_path, get_model_pool
        jit_path = find_silero_jit_path()
        get_model_pool().initialize(model, jit_path)
        
        dummy_input = torch.zeros(512, dtype=torch.float32)
        with torch.no_grad():
            _ = model(dummy_input.unsqueeze(0), 16000).item()
            
        set_silero_healthy(True)
        logger.info("[Startup] Silero VAD status: HEALTHY (Model Pool initialized)")
    except Exception as e:
        logger.warning(f"[Startup] Silero VAD status check FAILED ({e}). Falling back to Energy VAD.")
        set_silero_healthy(False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("\n--- Multilingual Voice Agent Backend ---")
    logger.info("Successfully started on http://localhost:8000")
    logger.info("WebSocket connections available at ws://localhost:8000/ws/audio")
    logger.info("---------------------------------\n")
    
    await check_silero_status()
    yield
    logger.info("--- Shutting down server ---")

app = FastAPI(title="Multilingual Voice Agent Platform Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transport_router)

@app.get("/")
async def root_check():
    return {"Status": "online", "message": "Multilingual Voice Agent Core Ingestion Layer Operational"}

@app.get("/api/clerk-key")
async def get_clerk_key():
    return {"publishable_key": settings.clerk_publishable_key}

if __name__ == "__main__":
    # Configure Uvicorn default logging layout with standard console printout + file mirrors
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": "%(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s",
                "use_colors": True,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "access_console": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/app.log",
                "maxBytes": 10485760,
                "backupCount": 5,
                "formatter": "default",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": settings.log_level, "propagate": False},
            "uvicorn.error": {"handlers": ["console", "file"], "level": settings.log_level, "propagate": False},
            "uvicorn.access": {"handlers": ["access_console"], "level": settings.log_level, "propagate": False},
        },
    }
    uvicorn.run(
        "backend.app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        log_level=settings.log_level.lower(),
        log_config=log_config
    )