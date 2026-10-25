from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from core.mcp.transports.streamable_http import (
    EndpointSecurityPolicy,
    MCPProtocolError,
    MCPTransportLimitError,
    MCPTransportSecurityError,
    StreamableHTTPMCPTransport,
)


def _public_resolver(_host: str) -> tuple[str, ...]:
    return ("93.184.216.34",)


@pytest.mark.asyncio
async def test_initialize_list_call_and_close_use_json_rpc_and_session_id() -> None:
    requests: list[tuple[str, dict[str, object], str | None]] = []
    request_hosts: list[tuple[str, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content or b"{}")
        requests.append(
            (request.method, payload, request.headers.get("mcp-session-id"))
        )
        request_hosts.append((str(request.url.host), request.headers.get("host")))
        if request.method == "DELETE":
            return httpx.Response(204)
        method = payload.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake", "version": "1"},
                    },
                },
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "lookup_order",
                                "description": "Lookup",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "string"}},
                                    "required": ["id"],
                                },
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"content": [{"type": "text", "text": "ready"}]},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc",
        client=client,
        endpoint_policy=EndpointSecurityPolicy(resolver=_public_resolver),
        credential_headers={"Authorization": "Bearer private-value"},
    )

    await transport.connect()
    tools = await transport.list_tools()
    result = await transport.call_tool(
        "lookup_order", {"id": "42"}, idempotency_key="session:turn:call"
    )
    await transport.close()
    await client.aclose()

    assert [tool.name for tool in tools] == ["lookup_order"]
    assert result.content == "ready"
    assert result.is_error is False
    assert requests[0][1]["method"] == "initialize"
    assert requests[1][1]["method"] == "notifications/initialized"
    assert requests[2][2] == "session-1"
    assert requests[3][1]["params"]["_meta"]["idempotencyKey"] == ("session:turn:call")
    assert requests[-1][0] == "DELETE"
    assert request_hosts[0] == ("93.184.216.34", "mcp.example.test")


def test_credential_headers_cannot_override_transport_security_headers() -> None:
    with pytest.raises(MCPTransportSecurityError):
        StreamableHTTPMCPTransport(
            "https://mcp.example.test/rpc",
            endpoint_policy=EndpointSecurityPolicy(resolver=_public_resolver),
            credential_headers={"Host": "attacker.example"},
        )


@pytest.mark.asyncio
async def test_malformed_protocol_and_oversized_result_fail_closed() -> None:
    responses = [
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, content=b"x" * 1025),
    ]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    policy = EndpointSecurityPolicy(resolver=_public_resolver)
    malformed = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc", client=client, endpoint_policy=policy
    )
    with pytest.raises(MCPProtocolError):
        await malformed.connect()

    oversized = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc",
        client=client,
        endpoint_policy=policy,
        max_response_bytes=1024,
    )
    with pytest.raises(MCPTransportLimitError):
        await oversized.connect()
    await client.aclose()


@pytest.mark.asyncio
async def test_redirect_timeout_and_cancellation_fail_closed() -> None:
    mode = "redirect"

    async def handler(_request: httpx.Request) -> httpx.Response:
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/mcp"})
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc",
        client=client,
        endpoint_policy=EndpointSecurityPolicy(resolver=_public_resolver),
        timeout_seconds=0.01,
    )
    with pytest.raises(MCPTransportSecurityError, match="redirect"):
        await transport.connect()

    mode = "slow"
    with pytest.raises(TimeoutError):
        await transport.connect()

    task = asyncio.create_task(transport.connect())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.aclose()


@pytest.mark.asyncio
async def test_credentials_are_not_exposed_in_errors_or_repr() -> None:
    secret = "Bearer private-value"

    async def handler(_request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"failure containing {secret}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = StreamableHTTPMCPTransport(
        "https://mcp.example.test/rpc",
        client=client,
        endpoint_policy=EndpointSecurityPolicy(resolver=_public_resolver),
        credential_headers={"Authorization": secret},
    )
    with pytest.raises(MCPProtocolError) as exc_info:
        await transport.connect()
    assert secret not in str(exc_info.value)
    assert secret not in repr(transport)
    await client.aclose()
