"""Provider-neutral LLM tool schema and streamed-call normalization."""

from __future__ import annotations

import json
from typing import Any

from core.providers.exceptions import (
    ProviderFailure,
    ProviderFailureCategory,
    ProviderInvocationError,
)
from core.providers.interfaces.llm import ToolDefinition


def serialize_tool_definitions(
    tools: list[ToolDefinition],
) -> list[dict[str, Any]]:
    """Convert internal definitions to OpenAI-compatible function schemas."""

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
                or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


class ToolCallAccumulator:
    """Accumulate fragmented OpenAI-compatible calls without leaking payloads."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self._calls: dict[int, dict[str, Any]] = {}

    def __bool__(self) -> bool:
        return bool(self._calls)

    def clear(self) -> None:
        self._calls.clear()

    def add(self, fragment: dict[str, Any]) -> None:
        index = int(fragment.get("index", 0))
        slot = self._calls.setdefault(
            index, {"id": None, "name": "", "arguments": ""}
        )
        call_id = fragment.get("id")
        if call_id:
            slot["id"] = str(call_id)
        function = fragment.get("function") or {}
        name = function.get("name")
        if name:
            slot["name"] += str(name)
        arguments = function.get("arguments")
        if arguments:
            slot["arguments"] += str(arguments)

    def finalize(self) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for index in sorted(self._calls):
            slot = self._calls[index]
            name = str(slot["name"]).strip()
            raw_arguments = str(slot["arguments"])
            if not name:
                raise self._invalid_output()
            try:
                arguments = json.loads(raw_arguments) if raw_arguments else {}
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise self._invalid_output() from exc
            if not isinstance(arguments, dict):
                raise self._invalid_output()
            calls.append(
                {
                    "id": slot["id"],
                    "name": name,
                    "arguments": arguments,
                }
            )
        return calls

    def _invalid_output(self) -> ProviderInvocationError:
        return ProviderInvocationError(
            ProviderFailure(
                provider_id=self.provider_id,
                category=ProviderFailureCategory.INVALID_OUTPUT,
                retryable=True,
            )
        )
