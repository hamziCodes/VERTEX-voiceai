"""UCVE Structured JSON Logger & Compliance Redaction Processors."""

from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any

from core.compliance.redaction import redact_log_fields, redact_text
from core.observability.context import ObservabilityContext

CORRELATION_KEYS = (
    "service",
    "request_id",
    "trace_id",
    "span_id",
    "call_id",
    "tenant_id",
    "session_id",
    "turn_id",
    "phase",
)


def redact_phi(text: str) -> str:
    """Redact sensitive PHI patterns (phone numbers, emails, SSNs) from text."""
    if not isinstance(text, str):
        return text
    return redact_text(text)


def redact_url_params(url: str) -> str:
    """Redact authentication token query parameters from URLs."""
    if not isinstance(url, str):
        return url
    return redact_text(url)


class StructuredJSONFormatter(logging.Formatter):
    """Format structured JSON logs with context and privacy redaction."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = ObservabilityContext.get()
        message = record.getMessage()

        # Apply redactions to message
        message = redact_phi(message)
        message = redact_url_params(message)

        log_data: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "event": message,
            "logger": record.name,
        }

        # Merge correlation IDs from context
        for key in CORRELATION_KEYS:
            if key in ctx:
                log_data[key] = ctx[key]

        # Merge extra attributes if passed
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            sanitized = redact_log_fields(record.extra_fields)
            if isinstance(sanitized, dict):
                log_data.update(sanitized)

        return json.dumps(log_data)


class StructuredLoggerWrapper:
    """Logger wrapper providing structured key-value logging API."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, kwargs)

    def _log(self, level: int, event: str, kwargs: dict[str, Any]) -> None:
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            event,
            (),
            None,
        )
        record.extra_fields = kwargs
        self._logger.handle(record)


_REDACTION_INSTALLED = False


def install_log_redaction() -> None:
    """Redact every log record in the process, whichever logger created it.

    Modules that use ``logging.getLogger`` directly (and third-party libraries)
    bypass :class:`StructuredJSONFormatter`. Wrapping the record factory makes
    the message, its ``%`` arguments and any formatted traceback pass through
    the same PII/credential redaction before any handler sees them.
    """
    global _REDACTION_INSTALLED
    if _REDACTION_INSTALLED:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        try:
            record.msg = redact_text(record.getMessage())
            record.args = None
        except Exception:  # noqa: BLE001 - a log line must never crash the caller
            record.msg = "[UNRENDERABLE LOG MESSAGE]"
            record.args = None
        if record.exc_info and record.exc_info[0] is not None:
            import traceback

            record.exc_text = redact_text(
                "".join(traceback.format_exception(*record.exc_info))
            ).rstrip("\n")
        return record

    logging.setLogRecordFactory(factory)
    _REDACTION_INSTALLED = True


_loggers: dict[str, StructuredLoggerWrapper] = {}


def get_logger(name: str = "ucve") -> StructuredLoggerWrapper:
    """Retrieve or create structured logger for module name."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

    wrapped = StructuredLoggerWrapper(logger)
    _loggers[name] = wrapped
    return wrapped
