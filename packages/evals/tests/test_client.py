from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from llm_evals.client import ChatError, ChatRequest, build_body, complete
from llm_evals.config import Backend, RequestOptions
from llm_evals.reply import Reply
from llm_evals.testing import Scripted, ScriptedServer

REQUEST = ChatRequest([{"role": "user", "content": "hi"}])


def test_body_merges_extra_body_last(backend: Backend, options: RequestOptions) -> None:
    request = ChatRequest(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function"}],
        response_format={"type": "json_object"},
    )
    body = build_body(backend, request, options)
    assert body == {
        "model": "fake-model",
        "messages": request.messages,
        "max_tokens": 64,
        "temperature": 0.0,
        "stream": False,
        "tools": [{"type": "function"}],
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    assert "tools" not in build_body(backend, REQUEST, options)


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
def test_reasoning_field_names_are_normalized(field: str) -> None:
    payload = {
        "choices": [{"message": {"content": " 42 ", field: "think"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5},
    }
    reply = Reply.from_openai(payload)
    assert (reply.content, reply.reasoning, reply.finish_reason) == ("42", "think", "stop")
    assert (reply.prompt_tokens, reply.completion_tokens) == (3, 5)


def test_inline_think_tags_are_split_off() -> None:
    payload = {"choices": [{"message": {"content": "<think>hmm</think>\n\nAnswer: 4"}}]}
    reply = Reply.from_openai(payload)
    assert (reply.content, reply.reasoning) == ("Answer: 4", "hmm")


def test_tool_call_arguments_are_kept_raw_or_encoded() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "a", "arguments": '{"x": 1}'}},
                        {"function": {"name": "b", "arguments": {"y": 2}}},
                    ],
                }
            }
        ]
    }
    reply = Reply.from_openai(payload)
    assert reply.content == ""
    assert [(c.name, c.arguments) for c in reply.tool_calls] == [
        ("a", '{"x": 1}'),
        ("b", '{"y": 2}'),
    ]


async def test_complete_returns_reply(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(lambda _: Scripted(content="Answer: 4", reasoning="2+2"))
    async with server.client() as client:
        reply = await complete(client, backend, REQUEST, options)
    assert (reply.content, reply.reasoning) == ("Answer: 4", "2+2")
    assert server.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}


async def test_connection_errors_are_retried(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(lambda _: "ok", connect_failures=2)
    async with server.client() as client:
        reply = await complete(client, backend, REQUEST, options)
    assert reply.content == "ok"
    assert len(server.requests) == 1


async def test_retries_are_bounded(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(lambda _: "ok", connect_failures=3)
    async with server.client() as client:
        with pytest.raises(ChatError, match="ConnectError"):
            await complete(client, backend, REQUEST, options)
    assert server.requests == []


async def test_http_errors_are_not_retried(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(lambda _: Scripted(status=500))
    async with server.client() as client:
        with pytest.raises(ChatError, match=r"HTTP 500: .*scripted failure"):
            await complete(client, backend, REQUEST, options)
    assert len(server.requests) == 1


async def test_timeouts_are_not_retried(backend: Backend, options: RequestOptions) -> None:
    server = ScriptedServer(lambda _: Scripted(content="late", delay_s=1.0))
    async with server.client() as client:
        with pytest.raises(ChatError, match=r"timed out after 0.05 s"):
            await complete(client, backend, REQUEST, replace(options, timeout_s=0.05))
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, text="<html>"), "response is not JSON"),
        (httpx.Response(200, json={"error": {"message": "boom"}}), "server error"),
    ],
)
async def test_unusable_bodies(
    backend: Backend, options: RequestOptions, response: httpx.Response, message: str
) -> None:
    transport = httpx.MockTransport(lambda _: response)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ChatError, match=message):
            await complete(client, backend, REQUEST, options)
