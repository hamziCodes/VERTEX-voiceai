"""UCVE Large Language Model (LLM) Provider Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from core.buffers.cancellation import CancellationToken


@dataclass
class ToolDefinition:
    """LLM or MCP tool definition contract."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """Configuration contract for LLM providers."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 512
    history_token_budget: int = 4096
    tools: list[ToolDefinition] = field(default_factory=list)


@dataclass(frozen=True)
class LLMStreamChunk:
    """LLM streaming response chunk."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    is_first_token: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider_id: str | None = None
    provider_request_id: str | None = None


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if provider is healthy and ready."""

    @abstractmethod
    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream LLM text and tool call chunks from prompt history."""
