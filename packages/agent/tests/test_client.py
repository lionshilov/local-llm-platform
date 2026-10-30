from __future__ import annotations

from typing import Any

import httpx
import pytest
from llm_agent.client import ChatClient, ModelError, parse_completion
from llm_agent.config import ClientConfig, ThinkingSwitch, deep_merge
from llm_agent.messages import Message
from pydantic import SecretStr


def completion(message: dict[str, Any], usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"choices": [{"message": message, "finish_reason": "stop"}], "usage": usage}


def test_parses_tool_calls_usage_and_reasoning() -> None:
    payload = completion(
        {
            "role": "assistant",
            "content": None,
            "reasoning": "thinking...",  # Ollama / MLX spelling
            "tool_calls": [
                {"id": "", "function": {"name": "f", "arguments": {"x": 1}}},  # quirks
                {"id": "c2", "type": "function", "function": {"name": "g", "arguments": "{}"}},
            ],
        },
        usage={"prompt_tokens": 50, "completion_tokens": 5, "prompt_tokens_details": None},
    )
    payload["timings"] = {"prompt_ms": 12.5, "predicted_ms": 80.0}
    result = parse_completion(payload, latency_s=0.5)

    assert result.message.content == ""
    assert result.reasoning == "thinking..."
    calls = result.message.tool_calls or []
    assert calls[0].id.startswith("call_")  # generated, so the result can reference it
    assert calls[0].function.arguments == '{"x": 1}'
    assert calls[1].id == "c2"
    assert result.usage.total_tokens == 55
    assert result.usage.cached_tokens == 0
    assert result.server_timings == {"prompt_ms": 12.5, "predicted_ms": 80.0}


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"error": {"message": "context overflow"}}, "server error"),
        ({"choices": []}, "not a chat completion"),
        ("nonsense", "not a chat completion"),
    ],
)
def test_bad_payloads_raise_model_error(payload: Any, error: str) -> None:
    with pytest.raises(ModelError, match=error):
        parse_completion(payload, latency_s=0)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(503, text="loading model"), "HTTP 503: loading model"),
        (httpx.Response(200, text="<html>"), "response is not JSON"),
    ],
)
async def test_http_failures_raise_model_error(
    config: ClientConfig, response: httpx.Response, error: str
) -> None:
    transport = httpx.MockTransport(lambda _: response)
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(ModelError, match=error):
            await ChatClient(config, http).complete([Message.user("hi")])


async def test_connection_errors_raise_model_error(config: ClientConfig) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        with pytest.raises(ModelError, match="ConnectError: connection refused"):
            await ChatClient(config, http).complete([Message.user("hi")])


async def test_api_key_is_sent_as_bearer_token(config: ClientConfig) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=completion({"role": "assistant", "content": "ok"}))

    config = config.model_copy(update={"api_key": SecretStr("sk-test")})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await ChatClient(config, http).complete([Message.user("hi")])

    assert seen[0].url == "http://fake/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer sk-test"
    assert "sk-test" not in repr(config)


@pytest.mark.parametrize(
    ("switch", "think", "expected"),
    [
        (
            ThinkingSwitch.PORTABLE,
            False,
            {"chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none"},
        ),
        (ThinkingSwitch.TEMPLATE, True, {"chat_template_kwargs": {"enable_thinking": True}}),
        (ThinkingSwitch.EFFORT, True, {"reasoning_effort": "medium"}),
        (ThinkingSwitch.NONE, False, {}),
    ],
)
def test_thinking_switch(switch: ThinkingSwitch, think: bool, expected: dict[str, Any]) -> None:
    assert ClientConfig(think=think, thinking_switch=switch).thinking_fields() == expected


def test_extra_body_is_merged_last_and_deeply() -> None:
    config = ClientConfig(
        extra_body={"temperature": 0.7, "chat_template_kwargs": {"add_vision_id": False}}
    )
    fields = config.request_fields()
    assert fields["temperature"] == 0.7
    assert fields["chat_template_kwargs"] == {"enable_thinking": False, "add_vision_id": False}
    assert deep_merge({"a": {"b": 1}}, {"a": 2}) == {"a": 2}
