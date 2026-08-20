"""UCVE Structured JSON Logger & Compliance Redaction Processors."""

from __future__ import annotations

import datetime
import json
import logging
import re
import sys
from typing import Any

from core.observability.context import ObservabilityContext

# Regex patterns for PHI and secret URL query parameter redaction
_PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_AUTH_PARAM_PATTERN = re.compile(r"((?:token|api_key|signature|access_token|jwt)=)[^&]*", re.IGNORECASE)


def redact_phi(text: str) -> str:
    """Redact sensitive PHI patterns (phone numbers, emails, SSNs) from text."""
    if not isinstance(text, str):
        return text
    cleaned = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    cleaned = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _SSN_PATTERN.sub("[REDACTED_SSN]", cleaned)
    return cleaned


def redact_url_params(url: str) -> str:
    """Redact authentication token query parameters from URLs."""
    if not isinstance(url, str):
        return url
    return _AUTH_PARAM_PATTERN.sub(r"\1[REDACTED]", url)


class StructuredJSONFormatter(logging.Formatter):
    """Formatter producing standardized JSON log records enriched with context variables."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = ObservabilityContext.get()
        message = record.getMessage()

        # Apply redactions to message
        message = redact_phi(message)
        message = redact_url_params(message)

        log_data: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc).isoformat(),
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
            for k, v in record.extra_fields.items():
                if isinstance(v, str):
                    v = redact_phi(redact_url_params(v))
                log_data[k] = v

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
        record.extra_fields = kwargs  # type: ignore[attr-defined]
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
