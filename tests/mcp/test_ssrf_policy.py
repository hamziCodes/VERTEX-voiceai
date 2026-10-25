from __future__ import annotations

import httpx
import pytest

from core.mcp.transports.streamable_http import (
    EndpointSecurityPolicy,
    MCPTransportSecurityError,
    StreamableHTTPMCPTransport,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "http://public.example.test/mcp",
        "https://localhost/mcp",
        "https://127.0.0.1/mcp",
        "https://[::1]/mcp",
        "https://169.254.169.254/latest/meta-data",
        "https://user:password@example.test/mcp",
    ],
)
async def test_protected_policy_rejects_unsafe_endpoints(endpoint: str) -> None:
    policy = EndpointSecurityPolicy(resolver=lambda _host: ("93.184.216.34",))
    with pytest.raises(MCPTransportSecurityError):
        await policy.validate(endpoint)


@pytest.mark.asyncio
async def test_dns_private_address_and_rebinding_are_rejected() -> None:
    answers = iter([("93.184.216.34",), ("10.0.0.8",)])
    policy = EndpointSecurityPolicy(resolver=lambda _host: next(answers))
    endpoint = "https://mcp.example.test/rpc"
    first = await policy.validate(endpoint)
    assert first == frozenset({"93.184.216.34"})
    with pytest.raises(MCPTransportSecurityError, match="address"):
        await policy.validate(endpoint, expected_addresses=first)


@pytest.mark.asyncio
async def test_enterprise_allowlist_can_authorize_private_target() -> None:
    policy = EndpointSecurityPolicy(
        resolver=lambda _host: ("10.0.0.8",),
        allowed_private_hosts=frozenset({"internal-mcp.example.test"}),
    )
    result = await policy.validate("https://internal-mcp.example.test/mcp")
    assert result == frozenset({"10.0.0.8"})


@pytest.mark.asyncio
async def test_transport_rechecks_dns_before_every_request() -> None:
    answers = iter([("93.184.216.34",), ("10.0.0.9",)])
    sent = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc",
        client=client,
        endpoint_policy=EndpointSecurityPolicy(resolver=lambda _host: next(answers)),
    )
    with pytest.raises(MCPTransportSecurityError):
        await transport.connect()
    assert sent == 0
    await client.aclose()
