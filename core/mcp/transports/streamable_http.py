"""Bounded MCP Streamable HTTP JSON-RPC transport."""

from __future__ import annotations

import asyncio
import inspect
import ipaddress
import json
import socket
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx

from core.providers.interfaces.llm import ToolDefinition

MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPProtocolError(RuntimeError):
    """Remote response did not satisfy the MCP JSON-RPC contract."""


class MCPTransportSecurityError(RuntimeError):
    """Endpoint or response violated the outbound transport policy."""


class MCPTransportLimitError(RuntimeError):
    """A bounded transport payload exceeded its platform cap."""


Resolver = Callable[[str], Iterable[str] | Awaitable[Iterable[str]]]


async def _system_resolver(host: str) -> tuple[str, ...]:
    def _resolve() -> tuple[str, ...]:
        rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return tuple(sorted({str(row[4][0]) for row in rows}))

    return await asyncio.to_thread(_resolve)


@dataclass(frozen=True, slots=True)
class EndpointSecurityPolicy:
    """Validate protected MCP endpoints and detect DNS answer changes."""

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
            raise MCPTransportSecurityError("MCP endpoint must use HTTPS.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise MCPTransportSecurityError("MCP endpoint URL is not allowed.")
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost"):
            raise MCPTransportSecurityError("MCP endpoint host is not allowed.")

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
                raise MCPTransportSecurityError(
                    "MCP endpoint resolved to an invalid address."
                ) from exc
        if not resolved:
            raise MCPTransportSecurityError("MCP endpoint did not resolve.")
        private_authorized = host in self.allowed_private_hosts
        if not private_authorized and any(
            not ipaddress.ip_address(item).is_global for item in resolved
        ):
            raise MCPTransportSecurityError(
                "MCP endpoint resolved to a blocked address."
            )
        if expected_addresses is not None and resolved != expected_addresses:
            raise MCPTransportSecurityError("MCP endpoint DNS answer changed.")
        return resolved


@dataclass(frozen=True, slots=True)
class MCPHTTPToolResult:
    content: str
    is_error: bool = False


class StreamableHTTPMCPTransport:
    """Protocol-correct JSON-RPC client with strict network and size bounds."""

    def __init__(
        self,
        endpoint: str,
        *,
        client: httpx.AsyncClient | None = None,
        endpoint_policy: EndpointSecurityPolicy | None = None,
        credential_headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 16 * 1024,
    ) -> None:
        if not 0 < timeout_seconds <= 3.0:
            raise ValueError("MCP timeout must be between 0 and 3 seconds.")
        if not 256 <= max_response_bytes <= 16 * 1024:
            raise ValueError("MCP response limit must be between 256 bytes and 16 KiB.")
        self.endpoint = endpoint
        self.endpoint_policy = endpoint_policy or EndpointSecurityPolicy()
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._client = client or httpx.AsyncClient(follow_redirects=False)
        self._owns_client = client is None
        self._credential_headers = _validated_credential_headers(
            credential_headers or {}
        )
        self._session_id: str | None = None
        self._addresses: frozenset[str] | None = None
        self._request_id = 0
        self._connected = False

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(endpoint={self.endpoint!r}, "
            f"connected={self._connected!r})"
        )

    async def connect(self) -> bool:
        self._addresses = await self.endpoint_policy.validate(self.endpoint)
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "wavia", "version": "1"},
            },
        )
        if (
            not isinstance(result.get("protocolVersion"), str)
            or not isinstance(result.get("capabilities"), dict)
            or not isinstance(result.get("serverInfo"), dict)
        ):
            raise MCPProtocolError("MCP initialize result is malformed.")
        await self._notification("notifications/initialized", {})
        self._connected = True
        return True

    async def list_tools(self) -> list[ToolDefinition]:
        self._require_connected()
        result = await self._rpc("tools/list", {})
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list) or len(raw_tools) > 256:
            raise MCPProtocolError("MCP tool inventory is malformed.")
        tools: list[ToolDefinition] = []
        names: set[str] = set()
        for item in raw_tools:
            if not isinstance(item, dict):
                raise MCPProtocolError("MCP tool definition is malformed.")
            name = item.get("name")
            description = item.get("description", "")
            schema = item.get("inputSchema")
            if (
                not isinstance(name, str)
                or not name.strip()
                or len(name) > 255
                or name in names
                or not isinstance(description, str)
                or len(description) > 1_000
                or not isinstance(schema, dict)
            ):
                raise MCPProtocolError("MCP tool definition is malformed.")
            names.add(name)
            tools.append(
                ToolDefinition(
                    name=name,
                    description=description,
                    parameters=schema,
                )
            )
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> MCPHTTPToolResult:
        self._require_connected()
        params: dict[str, Any] = {"name": name, "arguments": arguments}
        if idempotency_key:
            params["_meta"] = {"idempotencyKey": idempotency_key}
        result = await self._rpc("tools/call", params)
        content = result.get("content", [])
        if not isinstance(content, list):
            raise MCPProtocolError("MCP tool result is malformed.")
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                raise MCPProtocolError("MCP tool result is malformed.")
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        rendered = "\n".join(text_parts)
        if not rendered and "structuredContent" in result:
            rendered = json.dumps(
                result["structuredContent"], separators=(",", ":"), ensure_ascii=False
            )
        if len(rendered.encode("utf-8")) > self.max_response_bytes:
            raise MCPTransportLimitError("MCP tool result exceeds the response limit.")
        return MCPHTTPToolResult(
            content=rendered,
            is_error=bool(result.get("isError", False)),
        )

    async def close(self) -> None:
        try:
            if self._session_id and self._addresses is not None:
                await self._request("DELETE", None, expect_response=False)
        finally:
            self._connected = False
            self._session_id = None
            self._credential_headers.clear()
            if self._owns_client:
                await self._client.aclose()

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        response = await self._request("POST", payload, expect_response=True)
        if (
            not isinstance(response, dict)
            or response.get("jsonrpc") != "2.0"
            or response.get("id") != request_id
        ):
            raise MCPProtocolError("MCP JSON-RPC response is malformed.")
        if "error" in response:
            raise MCPProtocolError("MCP server returned a JSON-RPC error.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP JSON-RPC result is malformed.")
        return result

    async def _notification(self, method: str, params: dict[str, Any]) -> None:
        await self._request(
            "POST",
            {"jsonrpc": "2.0", "method": method, "params": params},
            expect_response=False,
        )

    async def _request(
        self,
        method: str,
        payload: dict[str, Any] | None,
        *,
        expect_response: bool,
    ) -> dict[str, Any] | None:
        if self._addresses is None:
            raise MCPProtocolError("MCP transport is not initialized.")
        await self.endpoint_policy.validate(
            self.endpoint, expected_addresses=self._addresses
        )
        try:
            return await asyncio.wait_for(
                self._request_once(method, payload, expect_response=expect_response),
                timeout=self.timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise
        except (MCPProtocolError, MCPTransportLimitError, MCPTransportSecurityError):
            raise
        except Exception as exc:
            raise MCPProtocolError("MCP request failed.") from exc

    async def _request_once(
        self,
        method: str,
        payload: dict[str, Any] | None,
        *,
        expect_response: bool,
    ) -> dict[str, Any] | None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self._credential_headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        parsed = urlsplit(self.endpoint)
        headers["Host"] = parsed.netloc
        async with self._client.stream(
            method,
            self._pinned_url(parsed),
            json=payload,
            headers=headers,
            follow_redirects=False,
            extensions={"sni_hostname": parsed.hostname},
        ) as response:
            if 300 <= response.status_code < 400:
                raise MCPTransportSecurityError("MCP redirects are not allowed.")
            if response.status_code >= 400:
                raise MCPProtocolError("MCP server returned an HTTP error.")
            session_id = response.headers.get("Mcp-Session-Id")
            if session_id:
                self._session_id = session_id[:255]
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > self.max_response_bytes:
                    raise MCPTransportLimitError(
                        "MCP response exceeds the configured limit."
                    )
            if not expect_response:
                return None
            content_type = response.headers.get("content-type", "")
            return self._decode_response(bytes(body), content_type)

    def _decode_response(self, body: bytes, content_type: str) -> dict[str, Any]:
        try:
            if content_type.lower().startswith("text/event-stream"):
                candidates = [
                    line[5:].strip()
                    for line in body.decode("utf-8").splitlines()
                    if line.startswith("data:")
                ]
                if not candidates:
                    raise ValueError
                value = json.loads(candidates[-1])
            else:
                value = json.loads(body)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise MCPProtocolError("MCP response is not valid JSON.") from exc
        if not isinstance(value, dict):
            raise MCPProtocolError("MCP response must be a JSON object.")
        return value

    def _require_connected(self) -> None:
        if not self._connected:
            raise MCPProtocolError("MCP transport is not connected.")

    def _pinned_url(self, parsed: SplitResult) -> str:
        if not self._addresses:
            raise MCPProtocolError("MCP endpoint has no validated address.")
        address = sorted(self._addresses)[0]
        host = f"[{address}]" if ":" in address else address
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))


def _validated_credential_headers(headers: Mapping[str, str]) -> dict[str, str]:
    reserved = {
        "accept",
        "connection",
        "content-length",
        "content-type",
        "host",
        "location",
        "mcp-session-id",
        "transfer-encoding",
    }
    validated: dict[str, str] = {}
    for name, value in headers.items():
        normalized = str(name).strip()
        rendered = str(value)
        if (
            not normalized
            or normalized.casefold() in reserved
            or "\r" in normalized
            or "\n" in normalized
            or "\r" in rendered
            or "\n" in rendered
        ):
            raise MCPTransportSecurityError("MCP credential header is not allowed.")
        validated[normalized] = rendered
    return validated
