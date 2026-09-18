"""Security headers middleware for control-plane API (Phase 32)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds hardened security headers to all HTTP responses according to OWASP ASVS baseline."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Baseline security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=()"

        path = request.url.path
        # Baseline Content-Security-Policy (allows Swagger / ReDoc docs UI when requested)
        if "/docs" in path or "/redoc" in path or "/openapi.json" in path:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        elif path.startswith("/demo") or path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' http: https:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "media-src 'self' blob: data:; "
                "connect-src 'self' ws: wss: http: https:; "
                "frame-ancestors 'self';"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"

        return response
