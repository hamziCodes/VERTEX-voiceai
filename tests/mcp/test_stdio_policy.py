from __future__ import annotations

import sys

import pytest

from core.mcp.transports.sse import MCPTransportUnavailableError, SSEMCPTransport
from core.mcp.transports.stdio import StdioMCPTransport


@pytest.mark.asyncio
async def test_stdio_is_denied_in_protected_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_MCP_ALLOW_STDIO", "true")
    transport = StdioMCPTransport(
        executable="python",
        arguments=("safe_server.py",),
        allowed_executables=frozenset({"python"}),
    )
    with pytest.raises(PermissionError, match="local development"):
        await transport.connect()


@pytest.mark.asyncio
async def test_stdio_requires_flag_and_executable_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "development")
    monkeypatch.delenv("UCVE_MCP_ALLOW_STDIO", raising=False)
    transport = StdioMCPTransport(
        executable="python",
        arguments=("safe_server.py",),
        allowed_executables=frozenset({"python"}),
    )
    with pytest.raises(PermissionError, match="disabled"):
        await transport.connect()

    monkeypatch.setenv("UCVE_MCP_ALLOW_STDIO", "true")
    denied = StdioMCPTransport(
        executable="python",
        arguments=("safe_server.py",),
        allowed_executables=frozenset({"node"}),
    )
    with pytest.raises(PermissionError, match="allowlist"):
        await denied.connect()


def test_stdio_rejects_shell_command_strings() -> None:
    with pytest.raises(ValueError, match="structured arguments"):
        StdioMCPTransport(executable="python safe_server.py")
    with pytest.raises(ValueError, match="shell metacharacters"):
        StdioMCPTransport(
            executable="python",
            arguments=("safe_server.py;whoami",),
            allowed_executables=frozenset({"python"}),
        )


@pytest.mark.asyncio
async def test_sse_transport_explicitly_fails_closed() -> None:
    transport = SSEMCPTransport("https://mcp.example.test/sse")
    with pytest.raises(MCPTransportUnavailableError, match="not supported"):
        await transport.connect()


@pytest.mark.asyncio
async def test_stdio_local_process_uses_json_rpc_without_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    server = tmp_path / "fake_mcp.py"
    server.write_text(
        """import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    method = request.get('method')
    if method == 'initialize':
        result = {
            'protocolVersion': '2025-06-18',
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'fake', 'version': '1'},
        }
    elif method == 'tools/list':
        result = {'tools': [{
            'name': 'echo',
            'description': 'Echo',
            'inputSchema': {'type': 'object'},
        }]}
    else:
        result = {'content': [{'type': 'text', 'text': 'local-ok'}]}
    response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
    print(json.dumps(response), flush=True)
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("UCVE_ENV", "development")
    monkeypatch.setenv("UCVE_MCP_ALLOW_STDIO", "true")
    transport = StdioMCPTransport(
        executable=sys.executable,
        arguments=(str(server),),
        allowed_executables=frozenset({sys.executable}),
    )

    await transport.connect()
    tools = await transport.list_tools()
    result = await transport.call_tool("echo", {"value": "hello"})
    await transport.close()

    assert [tool.name for tool in tools] == ["echo"]
    assert result.content == "local-ok"
