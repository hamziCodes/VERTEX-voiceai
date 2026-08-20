"""UCVE Async Context Variable Manager for Correlation Identifiers."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_ctx_var: ContextVar[dict[str, Any]] = ContextVar("observability_context", default={})


class ObservabilityContext:
    """Manager for async context variable binding (call_id, tenant_id, session_id)."""

    @classmethod
    def bind(cls, **kwargs: Any) -> None:
        """Bind key-value metadata to current async task context."""
        current = dict(_ctx_var.get())
        current.update(kwargs)
        _ctx_var.set(current)

    @classmethod
    def get(cls) -> dict[str, Any]:
        """Retrieve copy of current context metadata dictionary."""
        return dict(_ctx_var.get())

    @classmethod
    def clear(cls) -> None:
        """Clear all context metadata for current task."""
        _ctx_var.set({})

    @classmethod
    def set_call_id(cls, call_id: str) -> None:
        """Set call correlation ID."""
        cls.bind(call_id=call_id)

    @classmethod
    def set_tenant_id(cls, tenant_id: str) -> None:
        """Set tenant isolation ID."""
        cls.bind(tenant_id=tenant_id)

    @classmethod
    def set_session_id(cls, session_id: str) -> None:
        """Set session correlation ID."""
        cls.bind(session_id=session_id)


bind = ObservabilityContext.bind
get = ObservabilityContext.get
clear = ObservabilityContext.clear
set_call_id = ObservabilityContext.set_call_id
set_tenant_id = ObservabilityContext.set_tenant_id
set_session_id = ObservabilityContext.set_session_id
