"""Production assembly for controlled outbound calling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from core.db.repos.outbound_call_repo import PostgresOutboundCallRepository
from core.secrets.repository import PostgresSecretRepository
from core.secrets.vault import SecretVault
from telephony_gateway.outbound import OutboundCallService
from telephony_gateway.telnyx.client import CredentialResolvingTelnyxDialer


@dataclass(slots=True)
class OutboundRuntime:
    service: OutboundCallService
    http_client: httpx.AsyncClient

    async def close(self) -> None:
        await self.http_client.aclose()


def build_outbound_runtime(database: Any) -> OutboundRuntime | None:
    """Return no runtime unless an explicit secure media endpoint is configured."""

    media_url = (os.environ.get("UCVE_TELEPHONY_MEDIA_PUBLIC_URL") or "").strip()
    if not media_url:
        return None
    repository = PostgresOutboundCallRepository(
        database=database, media_stream_url=media_url
    )
    vault = SecretVault(repository=PostgresSecretRepository(database))
    http_client = httpx.AsyncClient(
        base_url="https://api.telnyx.com",
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    dialer = CredentialResolvingTelnyxDialer(vault=vault, http_client=http_client)
    return OutboundRuntime(
        service=OutboundCallService(
            repository=repository,
            dialer=dialer,
            policy_provider=repository,
        ),
        http_client=http_client,
    )
