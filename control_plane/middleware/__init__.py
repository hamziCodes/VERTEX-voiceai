"""Control plane middleware package."""

from control_plane.middleware.security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
