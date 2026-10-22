from __future__ import annotations

import json

import pytest

from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.exceptions import ProviderFailureCategory, ProviderInvocationError
from core.providers.interfaces.llm import LLMConfig, ToolDefinition
from core.providers.tool_calls import ToolCallAccumulator, serialize_tool_definitions


class _StreamingResponse:
    status_code = 200

    async def __aenter__(self) -> _StreamingResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def aread(self) -> bytes:
        return b""

    async def aclose(self) -> None:
        return None

    async def aiter_lines(self):
        fragments = [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "function": {
                                        "name": "lookup_",
                                        "arguments": '{"id":',
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "name": "order",
                                        "arguments": '"42"}',
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ]
        for fragment in fragments:
            yield f"data: {json.dumps(fragment)}"
        yield "data: [DONE]"


class _CaptureClient:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def stream(self, *_args: object, **kwargs: object) -> _StreamingResponse:
        self.payload = kwargs["json"]  # type: ignore[assignment]
        return _StreamingResponse()


def test_tool_definitions_serialize_to_provider_json() -> None:
    schemas = serialize_tool_definitions(
        [
            ToolDefinition(
                name="lookup_order",
                description="Look up one order",
                parameters={
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            )
        ]
    )

    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up one order",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            },
        }
    ]
    json.dumps(schemas)


def test_fragmented_multi_tool_calls_finalize_deterministically() -> None:
    acc = ToolCallAccumulator("groq")
    acc.add(
        {
            "index": 1,
            "id": "call-b",
            "function": {"name": "send_", "arguments": '{"to"'},
        }
    )
    acc.add(
        {
            "index": 0,
            "id": "call-a",
            "function": {"name": "lookup", "arguments": '{"id":'},
        }
    )
    acc.add(
        {
            "index": 1,
            "function": {"name": "email", "arguments": ':"a@b.com"}'},
        }
    )
    acc.add({"index": 0, "function": {"arguments": '"42"}'}})

    assert acc.finalize() == [
        {"id": "call-a", "name": "lookup", "arguments": {"id": "42"}},
        {"id": "call-b", "name": "send_email", "arguments": {"to": "a@b.com"}},
    ]


def test_malformed_tool_arguments_are_typed_invalid_output() -> None:
    acc = ToolCallAccumulator("openai")
    acc.add({"index": 0, "function": {"name": "delete_account", "arguments": "{"}})

    with pytest.raises(ProviderInvocationError) as exc_info:
        acc.finalize()

    assert exc_info.value.failure.category is ProviderFailureCategory.INVALID_OUTPUT
    assert "{" not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "model"),
    [
        (GroqLLMProvider, "openai/gpt-oss-120b"),
        (GeminiLLMProvider, "gemini-2.5-flash"),
        (OpenAILLMProvider, "gpt-4o-mini"),
    ],
)
async def test_all_llm_adapters_share_tool_schema_and_fragment_contract(
    monkeypatch: pytest.MonkeyPatch,
    provider_type: type,
    model: str,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")
    provider = provider_type(api_key="test", model=model)
    client = _CaptureClient()
    monkeypatch.setattr(provider, "_get_client", lambda: client)
    config = LLMConfig(
        model=model,
        tools=[
            ToolDefinition(
                name="lookup_order",
                description="Look up one order",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )

    chunks = [
        chunk
        async for chunk in provider.generate_stream(
            [{"role": "user", "content": "where is it"}], config
        )
    ]

    assert client.payload is not None
    assert client.payload["tools"] == serialize_tool_definitions(config.tools)
    json.dumps(client.payload)
    assert chunks[-1].tool_calls == [
        {"id": "call-1", "name": "lookup_order", "arguments": {"id": "42"}}
    ]
