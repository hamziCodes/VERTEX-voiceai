"""Unified Error Code Taxonomy & UCVE Exception Hierarchy."""

from __future__ import annotations

from enum import Enum


class UCVEErrorCode(str, Enum):
    """Categorized UCVE Error Codes."""

    # Auth & Quotas
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # Pipeline & Processing
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FSM_INVALID_TRANSITION = "FSM_INVALID_TRANSITION"
    BARGE_IN_FAILED = "BARGE_IN_FAILED"

    # Compliance
    HIPAA_BAA_REQUIRED = "HIPAA_BAA_REQUIRED"
    DATA_CLASSIFICATION_BLOCKED = "DATA_CLASSIFICATION_BLOCKED"

    # Telephony
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    TRUNK_UNAVAILABLE = "TRUNK_UNAVAILABLE"
    CALLER_ID_MISSING = "CALLER_ID_MISSING"

    # Post-Call
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    DISPATCH_FAILED = "DISPATCH_FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

    # Latency / SLO
    LATENCY_SLO_BREACH = "LATENCY_SLO_BREACH"

    # Internal
    INTERNAL_ERROR = "INTERNAL_ERROR"


class UCVEError(Exception):
    """Base exception for all domain errors within UCVE."""

    def __init__(
        self,
        code: UCVEErrorCode,
        message: str,
        details: dict | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
