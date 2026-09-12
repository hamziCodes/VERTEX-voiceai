"""UCVE Self-Hosted OpenAPI Docs and ReDoc Serving Module."""

from __future__ import annotations

from pathlib import Path
import yaml

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_FILE = REPO_ROOT / "openapi.yaml"


def register_self_hosted_docs(app: FastAPI) -> None:
    """Register self-hosted /docs and /redoc routes without relying on 3rd-party SaaS."""

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json() -> JSONResponse:
        if OPENAPI_FILE.is_file():
            content = yaml.safe_load(OPENAPI_FILE.read_text(encoding="utf-8"))
            return JSONResponse(content=content)
        return JSONResponse(content=app.openapi())

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="UCVE Voice Engine API Docs",
            swagger_favicon_url="/demo/favicon.ico",
        )

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="UCVE Voice Engine ReDoc",
            redoc_favicon_url="/demo/favicon.ico",
        )
