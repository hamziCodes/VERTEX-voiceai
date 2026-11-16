"""Self-hosted OpenAPI document, Swagger UI and ReDoc for the control plane.

``/openapi.json`` is always the running app's own schema. The repository's
``openapi.yaml`` is a generated copy of it (scripts/release/export_openapi.py),
so the served contract can never fall behind the code.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse


def register_self_hosted_docs(app: FastAPI) -> None:
    """Register self-hosted /docs and /redoc routes without relying on 3rd-party SaaS."""

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json() -> JSONResponse:
        return JSONResponse(content=app.openapi())

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="UCVE Voice Engine API Docs",
            swagger_favicon_url="/favicon.ico",
        )

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="UCVE Voice Engine ReDoc",
            redoc_favicon_url="/favicon.ico",
        )
