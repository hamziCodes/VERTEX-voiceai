from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


def _token(private_key: rsa.RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "user_01",
        "iss": "https://issuer.example.test/",
        "aud": "wavia-control-plane",
        "email": "person@example.test",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.asyncio
async def test_jwks_provider_verifies_signature_and_required_claims() -> None:
    from control_plane.auth.oidc_jwks import JWKSIdentityProvider, OIDCJWTConfig

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = JWKSIdentityProvider(
        OIDCJWTConfig(
            issuer="https://issuer.example.test/",
            jwks_url="https://issuer.example.test/.well-known/jwks.json",
            audience="wavia-control-plane",
        ),
        signing_key_resolver=lambda _token: private_key.public_key(),
    )

    claims = await provider.authenticate_token(_token(private_key))

    assert claims["sub"] == "user_01"
    assert claims["iss"] == "https://issuer.example.test/"
    assert claims["email"] == "person@example.test"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.example.test/"},
        {"aud": "another-api"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"sub": ""},
    ],
)
async def test_jwks_provider_rejects_invalid_tokens(overrides: dict[str, object]) -> None:
    from control_plane.auth.oidc_jwks import JWKSIdentityProvider, OIDCJWTConfig

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = JWKSIdentityProvider(
        OIDCJWTConfig(
            issuer="https://issuer.example.test/",
            jwks_url="https://issuer.example.test/.well-known/jwks.json",
            audience="wavia-control-plane",
        ),
        signing_key_resolver=lambda _token: private_key.public_key(),
    )

    with pytest.raises(ValueError, match="OIDC token validation failed"):
        await provider.authenticate_token(_token(private_key, **overrides))


def test_oidc_config_requires_complete_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from control_plane.auth.oidc_jwks import OIDCJWTConfig

    for name in ("OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_AUDIENCE"):
        monkeypatch.delenv(name, raising=False)
    assert OIDCJWTConfig.from_environment() is None

    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example.test/")
    with pytest.raises(ValueError, match="OIDC_JWKS_URL"):
        OIDCJWTConfig.from_environment()


def test_oidc_config_rejects_non_https_jwks_outside_localhost() -> None:
    from control_plane.auth.oidc_jwks import OIDCJWTConfig

    with pytest.raises(ValueError, match="HTTPS"):
        OIDCJWTConfig(
            issuer="https://issuer.example.test/",
            jwks_url="http://issuer.example.test/jwks.json",
        )
