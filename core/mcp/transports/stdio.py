"""Bounded local-only MCP stdio JSON-RPC transport."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from core.mcp.transports.streamable_http import (
    MCPHTTPToolResult,
    MCPProtocolError,
    MCPTransportLimitError,
)
from core.providers.interfaces.llm import ToolDefinition

_SHELL_META = re.compile(r"[;&|`$<>\r\n]")


class StdioMCPTransport:
    """Run an allowlisted local executable directly, without a shell."""

    def __init__(
        self,
        executable: str,
        arguments: Sequence[str] = (),
        *,
        allowed_executables: frozenset[str] = frozenset(),
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 16 * 1024,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        normalized = executable.strip()
        if not normalized or (
            any(char.isspace() for char in normalized)
            and not Path(normalized).is_file()
        ):
            raise ValueError("Stdio MCP requires executable and structured arguments.")
        if _SHELL_META.search(normalized) or any(
            _SHELL_META.search(arg) for arg in arguments
        ):
            raise ValueError("Stdio MCP arguments contain shell metacharacters.")
        if not 0 < timeout_seconds <= 3.0:
            raise ValueError("Stdio MCP timeout must be between 0 and 3 seconds.")
        self.executable = normalized
        self.arguments = tuple(arguments)
        self.allowed_executables = allowed_executables
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.environment = dict(environment or {})
        self.enabled = False
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def connect(self) -> bool:
        environment = (os.environ.get("UCVE_ENV") or "development").strip().lower()
        allowed_env = environment in {"dev", "development", "test"}
        flag = (os.environ.get("UCVE_MCP_ALLOW_STDIO") or "").strip().lower()
        if not allowed_env:
            raise PermissionError("Stdio MCP is restricted to local development.")
        if flag not in {"1", "true", "yes"}:
            raise PermissionError("Stdio MCP transport is disabled.")
        if self.executable not in self.allowed_executables:
            raise PermissionError("Stdio MCP executable is not in the allowlist.")
        child_env = self._safe_environment()
        self._process = await asyncio.create_subprocess_exec(
            self.executable,
            *self.arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=child_env,
        )
        await self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wavia", "version": "1"},
            },
        )
        await self._send(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )
        self.enabled = True
        return True

    async def list_tools(self) -> list[ToolDefinition]:
        result = await self._rpc("tools/list", {})
        raw = result.get("tools")
        if not isinstance(raw, list) or len(raw) > 256:
            raise MCPProtocolError("MCP stdio inventory is malformed.")
        tools: list[ToolDefinition] = []
        for item in raw:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("inputSchema"), dict)
            ):
                raise MCPProtocolError("MCP stdio tool definition is malformed.")
            tools.append(
                ToolDefinition(
                    name=item["name"],
                    description=str(item.get("description", "")),
                    parameters=item["inputSchema"],
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
        params: dict[str, Any] = {"name": name, "arguments": arguments}
        if idempotency_key:
            params["_meta"] = {"idempotencyKey": idempotency_key}
        result = await self._rpc("tools/call", params)
        content = result.get("content", [])
        if not isinstance(content, list):
            raise MCPProtocolError("MCP stdio tool result is malformed.")
        text = "\n".join(
            str(item["text"])
            for item in content
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        )
        return MCPHTTPToolResult(text, bool(result.get("isError", False)))

    async def close(self) -> None:
        process = self._process
        self._process = None
        self.enabled = False
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        response = await self._receive()
        if (
            response.get("jsonrpc") != "2.0"
            or response.get("id") != request_id
            or not isinstance(response.get("result"), dict)
            or "error" in response
        ):
            raise MCPProtocolError("MCP stdio JSON-RPC response is malformed.")
        return cast(dict[str, Any], response["result"])

    async def _send(self, payload: dict[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise MCPProtocolError("MCP stdio input is unavailable.")
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > self.max_response_bytes:
            raise MCPTransportLimitError("MCP stdio request exceeds the size limit.")
        process.stdin.write(encoded)
        await asyncio.wait_for(process.stdin.drain(), timeout=self.timeout_seconds)

    async def _receive(self) -> dict[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise MCPProtocolError("MCP stdio output is unavailable.")
        line = await asyncio.wait_for(
            process.stdout.readline(), timeout=self.timeout_seconds
        )
        if not line or len(line) > self.max_response_bytes:
            raise MCPTransportLimitError("MCP stdio response exceeds the size limit.")
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise MCPProtocolError("MCP stdio response is malformed.") from exc
        if not isinstance(value, dict):
            raise MCPProtocolError("MCP stdio response must be an object.")
        return value

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            raise MCPProtocolError("MCP stdio process is not running.")
        return self._process

    def _safe_environment(self) -> dict[str, str]:
        allowed_names = {"PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP"}
        base = {
            name: value for name, value in os.environ.items() if name in allowed_names
        }
        base.update(self.environment)
        return base
