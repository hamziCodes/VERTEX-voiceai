"""OIDC identity authentication without trusting tenant or role claims."""

from __future__ import annotations

from collections.abc import Mapping
from inspect import isawaitable
from typing import Annotated, Any

from fastapi import Header, HTTPException, Request

from control_plane.auth.oidc_hook import get_oidc_provider
from control_plane.studio.models import IdentityContext


async def resolve_identity_context(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> IdentityContext:
    """Validate an OIDC token and return identity-only claims."""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token or token.startswith("ucve_live_"):
        raise HTTPException(status_code=401, detail="OIDC authentication required.")
    try:
        provider = (
            getattr(request.app.state, "oidc_provider", None) or get_oidc_provider()
        )
        result = provider.authenticate_token(token)
        claims: Mapping[str, Any] = await result if isawaitable(result) else result
        if not isinstance(claims, Mapping):
            raise TypeError("OIDC provider returned invalid claims.")
        subject = claims.get("sub")
        issuer = claims.get("iss")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("OIDC subject is missing.")
        if not isinstance(issuer, str) or not issuer.strip():
            raise ValueError("OIDC issuer is missing.")
        email_claim = claims.get("email")
        email = email_claim if isinstance(email_claim, str) else None
        return IdentityContext(subject=subject, issuer=issuer, email=email)
    except HTTPException:
        raise
    except (KeyError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or unauthorized credential.",
        ) from exc
