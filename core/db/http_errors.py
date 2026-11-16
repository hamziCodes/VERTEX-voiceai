"""Answer database outages with a clean, retryable 503 on every HTTP service.

Without this, a lost database surfaced as a bare ``500 Internal Server Error``
(plain text) after the pool's wait expired. Clients and load balancers need a
JSON 503 with ``Retry-After`` they can act on; the failure is logged once,
without connection details.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("ucve.db")

DATABASE_UNAVAILABLE = {
    "detail": "The database is temporarily unavailable. Retry shortly.",
    "code": "DATABASE_UNAVAILABLE",
}


def database_outage_types() -> tuple[type[BaseException], ...]:
    """Exception types that mean "the database is unreachable right now"."""
    types: list[type[BaseException]] = []
    try:
        import psycopg

        types.append(psycopg.OperationalError)
    except ImportError:  # pragma: no cover - packaging failure
        pass
    try:
        from psycopg_pool import PoolTimeout

        types.append(PoolTimeout)
    except ImportError:  # pragma: no cover - packaging failure
        pass
    return tuple(types)


def install_database_error_handlers(app: FastAPI) -> None:
    async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        logger.warning(
            "database unavailable",
            extra={"route": request.url.path, "error_type": type(exc).__name__},
        )
        headers = {"Retry-After": "5"}
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            headers["X-Request-Id"] = str(request_id)
        return JSONResponse(status_code=503, content=DATABASE_UNAVAILABLE, headers=headers)

    for exc_type in database_outage_types():
        app.add_exception_handler(exc_type, database_unavailable)


