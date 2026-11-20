"""Standards-based JWT verification for external Studio identity providers."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError


SigningKeyResolver = Callable[[str], Any]


@dataclass(frozen=True, slots=True)
class OIDCJWTConfig:
    issuer: str
    jwks_url: str
    audience: str | None = None
    algorithms: tuple[str, ...] = ("RS256",)

    def __post_init__(self) -> None:
        issuer = self.issuer.strip()
        jwks_url = self.jwks_url.strip()
        if not issuer or not jwks_url:
            raise ValueError("OIDC issuer and JWKS URL are required.")
        parsed = urlparse(jwks_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("OIDC_JWKS_URL must use HTTPS outside localhost.")
        if not self.algorithms or any(item not in {"RS256", "RS384", "RS512"} for item in self.algorithms):
            raise ValueError("OIDC algorithms must be pinned to an approved RSA signature algorithm.")
        object.__setattr__(self, "issuer", issuer)
        object.__setattr__(self, "jwks_url", jwks_url)
        if self.audience is not None:
            audience = self.audience.strip()
            object.__setattr__(self, "audience", audience or None)

    @classmethod
    def from_environment(cls) -> OIDCJWTConfig | None:
        issuer = (os.environ.get("OIDC_ISSUER") or "").strip()
        jwks_url = (os.environ.get("OIDC_JWKS_URL") or "").strip()
        audience = (os.environ.get("OIDC_AUDIENCE") or "").strip() or None
        if not issuer and not jwks_url and audience is None:
            return None
        missing = [
            name
            for name, value in (("OIDC_ISSUER", issuer), ("OIDC_JWKS_URL", jwks_url))
            if not value
        ]
        if missing:
            raise ValueError(f"Incomplete OIDC configuration; missing {', '.join(missing)}.")
        return cls(issuer=issuer, jwks_url=jwks_url, audience=audience)


class JWKSIdentityProvider:
    """Validate bearer JWTs against a pinned issuer and remote JWKS."""

    def __init__(
        self,
        config: OIDCJWTConfig,
        *,
        signing_key_resolver: SigningKeyResolver | None = None,
    ) -> None:
        self._config = config
        self._jwks_client = PyJWKClient(config.jwks_url, cache_keys=True, lifespan=300)
        self._resolve_key = signing_key_resolver or self._resolve_jwks_key

    def _resolve_jwks_key(self, token: str) -> Any:
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def _decode(self, token: str) -> Mapping[str, Any]:
        try:
            key = self._resolve_key(token)
            options = {
                "require": ["exp", "iat", "iss", "sub"],
                "verify_aud": self._config.audience is not None,
            }
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self._config.algorithms),
                issuer=self._config.issuer,
                audience=self._config.audience,
                options=options,
            )
            if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
                raise ValueError("OIDC subject is missing.")
            return claims
        except (PyJWTError, TypeError, ValueError) as exc:
            raise ValueError("OIDC token validation failed.") from exc

    async def authenticate_token(self, token: str) -> Mapping[str, Any]:
        if not token:
            raise ValueError("OIDC token validation failed.")
        return await asyncio.to_thread(self._decode, token)


def build_oidc_provider_from_environment() -> JWKSIdentityProvider | None:
    config = OIDCJWTConfig.from_environment()
    return JWKSIdentityProvider(config) if config is not None else None
