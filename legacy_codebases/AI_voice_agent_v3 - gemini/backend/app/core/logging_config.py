"""
Centralized logging setup.

Produces:
  logs/app.log            - everything, rotating, DEBUG level (the full firehose, on disk not console)
  logs/vad_frames.log     - ONLY the per-frame Silero probability dump (isolated, opt-in noise)
  logs/sessions/<id>.log  - ONE file per WebSocket call, attached/detached at connect/disconnect,
                            containing every log line emitted during that call across all modules.
                            This is the file to read after a barge-in test.

Console stays at INFO and short-format, so you're not scrolling — you just tail the relevant file.
"""
import logging
import logging.handlers
from pathlib import Path

# Calculate logs directory relative to this config file:
# This file is in project_root/backend/app/core/logging_config.py
# parents[3] gets project_root
LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
SESSIONS_DIR = LOGS_DIR / "sessions"


def setup_logging(console_level: str = "INFO") -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers below filter per-destination
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console — short, high-signal only
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Full rotating app log — everything, on disk
    app_file = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    app_file.setLevel(logging.DEBUG)
    app_file.setFormatter(fmt)
    root.addHandler(app_file)

    # VAD per-frame firehose — isolated logger, does NOT propagate to root/console/app.log
    vad_logger = logging.getLogger("vad.frames")
    vad_logger.setLevel(logging.DEBUG)
    vad_logger.propagate = False
    vad_file = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "vad_frames.log", maxBytes=20_000_000, backupCount=3, encoding="utf-8"
    )
    vad_file.setLevel(logging.DEBUG)
    vad_file.setFormatter(fmt)
    vad_logger.addHandler(vad_file)


def attach_session_log(session_id: str) -> logging.FileHandler:
    """Call on WS connect. Every log line from ANY module during this call
    (including vad.frames, since we attach to the root AND vad logger)
    gets mirrored into logs/sessions/<session_id>.log."""
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.FileHandler(SESSIONS_DIR / f"{session_id}.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)

    logging.getLogger().addHandler(handler)
    logging.getLogger("vad.frames").addHandler(handler)  # mirror frame dump into this session's file too
    return handler


def detach_session_log(handler: logging.FileHandler) -> None:
    """Call on WS disconnect."""
    logging.getLogger().removeHandler(handler)
    logging.getLogger("vad.frames").removeHandler(handler)
    handler.close()
