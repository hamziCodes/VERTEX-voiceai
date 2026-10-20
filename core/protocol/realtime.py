"""Canonical Wavia realtime envelope and version negotiation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

PROTOCOL_VERSION = "1.0.0"
SUPPORTED_PROTOCOL_RANGE = ">=1.0.0 <2.0.0"


class ProtocolCompatibilityError(ValueError):
    """Raised when a client speaks an unsupported protocol major."""

    code = "PROTOCOL_VERSION_UNSUPPORTED"
    supported_range = SUPPORTED_PROTOCOL_RANGE

    def __init__(self, client_version: str) -> None:
        self.client_version = client_version
        super().__init__(
            f"{self.code}: client {client_version!r}; supported {self.supported_range}"
        )


@dataclass(frozen=True, slots=True)
class ProtocolNegotiation:
    """Successful protocol selection for one connection."""

    client_version: str
    protocol_version: str = PROTOCOL_VERSION
    supported_range: str = SUPPORTED_PROTOCOL_RANGE


def _major(version: str) -> int:
    try:
        value = version.strip().split(".", 1)[0]
        major = int(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProtocolCompatibilityError(str(version)) from exc
    if major < 0:
        raise ProtocolCompatibilityError(version)
    return major


def negotiate_protocol(client_version: str) -> ProtocolNegotiation:
    """Accept compatible v1 minors and reject incompatible majors."""

    if _major(client_version) != _major(PROTOCOL_VERSION):
        raise ProtocolCompatibilityError(client_version)
    return ProtocolNegotiation(client_version=client_version)


def build_event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    sequence: int,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Create the canonical JSON event envelope."""

    if sequence < 1:
        raise ValueError("sequence must be at least 1")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": event_id or str(uuid4()),
        "sequence": sequence,
        "event_type": event_type,
        "timestamp_ms": time.time() * 1000.0,
        "payload": payload or {},
    }
