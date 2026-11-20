"""Tenant-scoped MCP host with authorization, schema, and timeout bounds."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from core.providers.interfaces.llm import ToolDefinition


class MCPTransportType(StrEnum):
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"
    STDIO = "stdio"


class MCPConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolTimeoutConfig:
    timeout_ms: int = 3_000
    fallback_utterance: str = "Let me check on that and get back to you"

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_ms <= 3_000:
            raise ValueError("MCP tool timeout must be between 1 and 3000 ms.")


@dataclass(slots=True)
class MCPServerConfig:
    """Persistable MCP metadata. Secret values never belong in this model."""

    server_id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    name: str = "MCP server"
    transport: MCPTransportType = MCPTransportType.STREAMABLE_HTTP
    endpoint: str = "https://mcp.invalid/rpc"
    allowed_tools: tuple[str, ...] = ()
    credential_ref: str | None = None
    enabled: bool = False
    side_effecting_tools: tuple[str, ...] = ()
    idempotency_supported_tools: tuple[str, ...] = ()
    stdio_executable: str | None = None
    stdio_arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.endpoint = self.endpoint.strip()
        self.allowed_tools = _normalized_names(self.allowed_tools)
        self.side_effecting_tools = _normalized_names(self.side_effecting_tools)
        self.idempotency_supported_tools = _normalized_names(
            self.idempotency_supported_tools
        )
        if not self.name or len(self.name) > 255:
            raise ValueError("MCP server name must contain 1 to 255 characters.")
        if self.transport is MCPTransportType.STREAMABLE_HTTP and not self.endpoint:
            raise ValueError("Streamable HTTP MCP requires an endpoint.")
        if self.transport is MCPTransportType.STREAMABLE_HTTP:
            parsed = urlsplit(self.endpoint)
            if (
                parsed.scheme.lower() != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
                or len(self.endpoint) > 2_048
            ):
                raise ValueError("Streamable HTTP MCP endpoint is not allowed.")
        if self.credential_ref is not None:
            self.credential_ref = self.credential_ref.strip() or None
            if self.credential_ref is not None and len(self.credential_ref) > 255:
                raise ValueError("MCP credential reference is too long.")
        allowed = set(self.allowed_tools)
        if not set(self.side_effecting_tools).issubset(allowed):
            raise ValueError("Side-effecting MCP tools must be explicitly allowed.")
        if not set(self.idempotency_supported_tools).issubset(allowed):
            raise ValueError("Idempotent MCP tools must be explicitly allowed.")


@dataclass(frozen=True, slots=True)
class MCPToolResult:
    content: str
    is_error: bool = False
    execution_time_ms: float = 0.0


class MCPTransport(Protocol):
    async def connect(self) -> bool: ...

    async def list_tools(self) -> list[ToolDefinition]: ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any: ...

    async def close(self) -> None: ...


CredentialResolver = Callable[
    [UUID, str], Mapping[str, str] | Awaitable[Mapping[str, str]]
]


class MCPHost:
    """Own one authorized MCP connection and its validated tool inventory."""

    def __init__(
        self,
        config: MCPServerConfig,
        timeout_config: ToolTimeoutConfig | None = None,
        *,
        transport: MCPTransport | None = None,
        credential_resolver: CredentialResolver | None = None,
        stdio_executable_allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self.config = config
        self.timeout_config = timeout_config or ToolTimeoutConfig()
        self._transport = transport
        self._credential_resolver = credential_resolver
        self._stdio_executable_allowlist = stdio_executable_allowlist
        self._inventory: dict[str, ToolDefinition] = {}
        self.is_connected = False

    async def connect(self) -> bool:
        if not self.config.enabled:
            raise MCPConfigurationError("MCP server is disabled.")
        if self._transport is None:
            self._transport = await self._build_transport()
        await self._transport.connect()
        self.is_connected = True
        try:
            await self.list_tools(refresh=True)
        except Exception:
            await self.close()
            raise
        return True

    async def list_tools(self, *, refresh: bool = False) -> list[ToolDefinition]:
        transport = self._require_transport()
        if refresh or not self._inventory:
            offered = await transport.list_tools()
            allowed = set(self.config.allowed_tools)
            selected = [tool for tool in offered if tool.name in allowed]
            if len({tool.name for tool in selected}) != len(selected):
                raise MCPConfigurationError("MCP inventory contains duplicate names.")
            for tool in selected:
                validate_tool_schema(tool.parameters)
            self._inventory = {tool.name: tool for tool in selected}
        return list(self._inventory.values())

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> MCPToolResult:
        if not self.is_connected:
            return _error_result("MCP server is not connected.")
        definition = self._inventory.get(name)
        if definition is None or name not in self.config.allowed_tools:
            return _error_result("MCP tool is not enabled for this server.")
        try:
            encoded = json.dumps(
                arguments, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        except (TypeError, ValueError):
            return _error_result("MCP tool arguments are invalid.")
        if len(encoded) > 8 * 1024:
            return _error_result("MCP tool arguments exceed the size limit.")
        try:
            validate_tool_arguments(arguments, definition.parameters)
        except ValueError:
            return _error_result("MCP tool arguments are invalid.")
        if name in self.config.side_effecting_tools:
            if name not in self.config.idempotency_supported_tools:
                return _error_result("MCP side effect lacks idempotency support.")
            if not idempotency_key or len(idempotency_key) > 255:
                return _error_result("MCP side effect requires an idempotency key.")

        started = time.monotonic()
        try:
            raw = await asyncio.wait_for(
                self._exec_tool(name, arguments, idempotency_key=idempotency_key),
                timeout=self.timeout_config.timeout_ms / 1000.0,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return MCPToolResult(
                content=(
                    f"Error: Tool '{name}' timed out after "
                    f"{self.timeout_config.timeout_ms} ms. "
                    f"{self.timeout_config.fallback_utterance}"
                ),
                is_error=True,
                execution_time_ms=float(self.timeout_config.timeout_ms),
            )
        except Exception:
            return _error_result("MCP tool execution failed.")
        content = str(getattr(raw, "content", ""))
        if len(content.encode("utf-8")) > 16 * 1024:
            return _error_result("MCP tool result exceeds the size limit.")
        return MCPToolResult(
            content=content,
            is_error=bool(getattr(raw, "is_error", False)),
            execution_time_ms=(time.monotonic() - started) * 1_000,
        )

    async def close(self) -> None:
        transport = self._transport
        self.is_connected = False
        self._inventory.clear()
        if transport is not None:
            await transport.close()

    async def _exec_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        return await self._require_transport().call_tool(
            name, arguments, idempotency_key=idempotency_key
        )

    async def _build_transport(self) -> MCPTransport:
        if self.config.transport is MCPTransportType.SSE:
            from core.mcp.transports.sse import SSEMCPTransport

            return SSEMCPTransport(self.config.endpoint)
        if self.config.transport is MCPTransportType.STDIO:
            from core.mcp.transports.stdio import StdioMCPTransport

            if not self.config.stdio_executable:
                raise MCPConfigurationError("Stdio MCP executable is not configured.")
            return StdioMCPTransport(
                self.config.stdio_executable,
                self.config.stdio_arguments,
                allowed_executables=self._stdio_executable_allowlist,
            )
        from core.mcp.transports.streamable_http import StreamableHTTPMCPTransport

        headers: Mapping[str, str] = {}
        if self.config.credential_ref:
            if self._credential_resolver is None:
                raise MCPConfigurationError("MCP credential resolver is unavailable.")
            resolved = self._credential_resolver(
                self.config.tenant_id, self.config.credential_ref
            )
            if inspect.isawaitable(resolved):
                resolved = await resolved
            headers = dict(resolved)
        return StreamableHTTPMCPTransport(
            self.config.endpoint,
            credential_headers=headers,
            timeout_seconds=self.timeout_config.timeout_ms / 1000.0,
        )

    def _require_transport(self) -> MCPTransport:
        if self._transport is None or not self.is_connected:
            raise MCPConfigurationError("MCP server is not connected.")
        return self._transport


def validate_tool_schema(schema: dict[str, Any]) -> None:
    encoded = json.dumps(schema, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    if len(encoded) > 16 * 1024:
        raise MCPConfigurationError("MCP tool schema exceeds the size limit.")
    if schema.get("type") != "object":
        raise MCPConfigurationError("MCP tool schema root must be an object.")
    _validate_schema_node(schema, depth=0)


def validate_tool_arguments(arguments: Any, schema: dict[str, Any]) -> None:
    _validate_value(arguments, schema, depth=0)


def _validate_schema_node(schema: Any, *, depth: int) -> None:
    if depth > 8 or not isinstance(schema, dict):
        raise MCPConfigurationError("MCP tool schema is invalid.")
    if "$ref" in schema or "$dynamicRef" in schema:
        raise MCPConfigurationError("MCP tool schema references are not allowed.")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict) or len(properties) > 128:
        raise MCPConfigurationError("MCP tool schema properties are invalid.")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
        raise MCPConfigurationError("MCP tool schema requirements are invalid.")
    for child in properties.values():
        _validate_schema_node(child, depth=depth + 1)
    items = schema.get("items")
    if items is not None:
        _validate_schema_node(items, depth=depth + 1)


def _validate_value(value: Any, schema: dict[str, Any], *, depth: int) -> None:
    if depth > 8:
        raise ValueError("nested_too_deep")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("enum")
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError("type")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if any(name not in value for name in required):
            raise ValueError("required")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError("additional_properties")
        for name, item in value.items():
            child = properties.get(name)
            if isinstance(child, dict):
                _validate_value(item, child, depth=depth + 1)
    elif expected == "array":
        if not isinstance(value, list):
            raise ValueError("type")
        if len(value) > int(schema.get("maxItems", 128)):
            raise ValueError("max_items")
        child = schema.get("items", {})
        if isinstance(child, dict):
            for item in value:
                _validate_value(item, child, depth=depth + 1)
    elif expected == "string":
        if not isinstance(value, str):
            raise ValueError("type")
        if len(value) < int(schema.get("minLength", 0)):
            raise ValueError("min_length")
        if len(value) > int(schema.get("maxLength", 8_192)):
            raise ValueError("max_length")
    elif expected == "integer" and (
        not isinstance(value, int) or isinstance(value, bool)
    ):
        raise ValueError("type")
    elif expected == "number" and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        raise ValueError("type")
    elif expected == "boolean" and not isinstance(value, bool):
        raise ValueError("type")


def _normalized_names(values: Any) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    )
    if len(normalized) > 256 or any(len(item) > 255 for item in normalized):
        raise ValueError("MCP tool allowlist is invalid.")
    return normalized


def _error_result(message: str) -> MCPToolResult:
    return MCPToolResult(content=message, is_error=True)
