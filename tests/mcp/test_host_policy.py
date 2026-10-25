from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from core.mcp.host import MCPConfigurationError, MCPHost, MCPServerConfig
from core.mcp.orchestrator import ToolOrchestrator
from core.providers.interfaces.llm import ToolDefinition


class _Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.closed = False

    async def connect(self) -> bool:
        return True

    async def list_tools(self) -> list[ToolDefinition]:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"id": {"type": "string", "maxLength": 20}},
            "required": ["id"],
        }
        return [
            ToolDefinition("lookup_order", "Lookup", schema),
            ToolDefinition("create_booking", "Book", schema),
            ToolDefinition("not_allowed", "Blocked", {"type": "object"}),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        self.calls.append((name, arguments, idempotency_key))
        return SimpleNamespace(content="ok", is_error=False)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_host_intersects_inventory_and_validates_arguments() -> None:
    transport = _Transport()
    host = MCPHost(
        MCPServerConfig(
            tenant_id=uuid4(),
            enabled=True,
            allowed_tools=("lookup_order",),
        ),
        transport=transport,
    )
    await host.connect()

    assert [tool.name for tool in await host.list_tools()] == ["lookup_order"]
    blocked = await host.call_tool("not_allowed", {})
    invalid = await host.call_tool("lookup_order", {"unexpected": "x"})
    valid = await host.call_tool("lookup_order", {"id": "42"})

    assert blocked.is_error is True
    assert invalid.is_error is True
    assert valid.content == "ok"
    assert transport.calls == [("lookup_order", {"id": "42"}, None)]
    await host.close()
    assert transport.closed is True


@pytest.mark.asyncio
async def test_side_effect_requires_and_forwards_idempotency_key() -> None:
    transport = _Transport()
    host = MCPHost(
        MCPServerConfig(
            tenant_id=uuid4(),
            enabled=True,
            allowed_tools=("create_booking",),
            side_effecting_tools=("create_booking",),
            idempotency_supported_tools=("create_booking",),
        ),
        transport=transport,
    )
    await host.connect()

    denied = await host.call_tool("create_booking", {"id": "42"})
    accepted = await host.call_tool(
        "create_booking",
        {"id": "42"},
        idempotency_key="session:turn:call",
    )

    assert denied.is_error is True
    assert accepted.is_error is False
    assert transport.calls == [("create_booking", {"id": "42"}, "session:turn:call")]


@pytest.mark.asyncio
async def test_disabled_server_and_missing_credential_resolver_fail_closed() -> None:
    disabled = MCPHost(MCPServerConfig(tenant_id=uuid4()))
    with pytest.raises(MCPConfigurationError, match="disabled"):
        await disabled.connect()

    configured = MCPHost(
        MCPServerConfig(
            tenant_id=uuid4(),
            enabled=True,
            credential_ref="tenant-secret-reference",
        )
    )
    with pytest.raises(MCPConfigurationError, match="resolver"):
        await configured.connect()


@pytest.mark.asyncio
async def test_orchestrator_routes_to_exact_tool_owner_and_closes_hosts() -> None:
    first_transport = _Transport()
    second_transport = _Transport()
    first = MCPHost(
        MCPServerConfig(
            tenant_id=uuid4(), enabled=True, allowed_tools=("lookup_order",)
        ),
        transport=first_transport,
    )
    second = MCPHost(
        MCPServerConfig(
            tenant_id=uuid4(), enabled=True, allowed_tools=("create_booking",)
        ),
        transport=second_transport,
    )
    await first.connect()
    await second.connect()
    orchestrator = ToolOrchestrator([first, second])

    await orchestrator.get_external_tools()
    result = await orchestrator.execute_tool_call_serially(
        "create_booking",
        {"id": "42"},
        idempotency_key="session:turn:call",
    )

    assert result["is_error"] is False
    assert first_transport.calls == []
    assert second_transport.calls == [
        ("create_booking", {"id": "42"}, "session:turn:call")
    ]
    await orchestrator.close()
    assert first_transport.closed is True
    assert second_transport.closed is True


@pytest.mark.asyncio
async def test_orchestrator_rejects_duplicate_tool_owners() -> None:
    hosts = [
        MCPHost(
            MCPServerConfig(
                tenant_id=uuid4(), enabled=True, allowed_tools=("lookup_order",)
            ),
            transport=_Transport(),
        )
        for _ in range(2)
    ]
    for host in hosts:
        await host.connect()

    with pytest.raises(MCPConfigurationError, match="Duplicate MCP tool owner"):
        await ToolOrchestrator(hosts).get_external_tools()
