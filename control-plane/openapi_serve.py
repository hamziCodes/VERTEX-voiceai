"""Compatibility shim for Phase 28 layout checks. Canonical package: control_plane.openapi_serve."""

from __future__ import annotations

from control_plane.openapi_serve import register_self_hosted_docs

__all__ = ["register_self_hosted_docs"]
