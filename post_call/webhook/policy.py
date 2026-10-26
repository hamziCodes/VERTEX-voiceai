"""Outbound destination policy for post-call webhooks."""

from __future__ import annotations

import inspect
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit


class WebhookSecurityError(ValueError):
    pass


Resolver = Callable[[str], Iterable[str] | Awaitable[Iterable[str]]]


async def _system_resolver(host: str) -> tuple[str, ...]:
    def _resolve() -> tuple[str, ...]:
        rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return tuple(sorted({str(row[4][0]) for row in rows}))

    import asyncio

    return await asyncio.to_thread(_resolve)


@dataclass(frozen=True, slots=True)
class WebhookEndpointPolicy:
    resolver: Resolver = _system_resolver
    allowed_private_hosts: frozenset[str] = frozenset()

    async def validate(
        self,
        endpoint: str,
        *,
        expected_addresses: frozenset[str] | None = None,
    ) -> frozenset[str]:
        parsed = urlsplit(endpoint)
        if parsed.scheme.lower() != "https":
            raise WebhookSecurityError("Webhook endpoint must use HTTPS.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise WebhookSecurityError("Webhook endpoint URL is not allowed.")
        if parsed.port not in {None, 443}:
            raise WebhookSecurityError("Webhook endpoint port is not allowed.")
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost"):
            raise WebhookSecurityError("Webhook endpoint host is not allowed.")

        try:
            literal = ipaddress.ip_address(host)
            resolved = frozenset({str(literal)})
        except ValueError:
            answer = self.resolver(host)
            if inspect.isawaitable(answer):
                answer = await answer
            try:
                resolved = frozenset(str(ipaddress.ip_address(item)) for item in answer)
            except ValueError as exc:
                raise WebhookSecurityError(
                    "Webhook endpoint resolved to an invalid address."
                ) from exc
        if not resolved:
            raise WebhookSecurityError("Webhook endpoint did not resolve.")
        if host not in self.allowed_private_hosts and any(
            not ipaddress.ip_address(item).is_global for item in resolved
        ):
            raise WebhookSecurityError(
                "Webhook endpoint resolved to a blocked address."
            )
        if expected_addresses is not None and resolved != expected_addresses:
            raise WebhookSecurityError("Webhook endpoint DNS answer changed.")
        return resolved
