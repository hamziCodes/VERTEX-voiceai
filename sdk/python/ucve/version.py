"""UCVE Python SDK Version Manifest."""

from __future__ import annotations

from .protocol_generated import PROTOCOL_VERSION

SDK_VERSION_MANIFEST = {
    "api_version": "1.0.0",
    "event_schema_version": PROTOCOL_VERSION,
    "min_server_version": "0.1.0",
}

__version__ = "1.0.4"
