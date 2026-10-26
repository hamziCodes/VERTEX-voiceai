"""UCVE Structured JSON Logger & Compliance Redaction Processors."""

from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any

from core.compliance.redaction import redact_sensitive_data, redact_text
from core.observability.context import ObservabilityContext


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
        for key in ("call_id", "tenant_id", "session_id", "phase"):
            if key in ctx:
                log_data[key] = ctx[key]

        # Merge extra attributes if passed
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            sanitized = redact_sensitive_data(record.extra_fields)
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
