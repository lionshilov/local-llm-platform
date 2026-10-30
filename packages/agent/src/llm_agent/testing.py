"""A scripted fake OpenAI-compatible server for tests, built on ``httpx.MockTransport``.

Each chat request is answered with the next scripted assistant message, so a test reads
like the conversation it simulates::

    server = ScriptedServer([
        call_tools(tool_call("calculator", {"expression": "6 * 7"})),
        answer("6 * 7 = 42"),
    ])
    result = await Agent(config, [calculator], http_client=server.client()).run("6 * 7?")
    assert server.requests[1]["messages"][-1]["content"] == "42"
"""

from __future__ import annotations

import asyncio
import itertools
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

_call_ids = itertools.count(1)


def tool_call(
    name: str, arguments: dict[str, Any] | str, *, call_id: str | None = None
) -> dict[str, Any]:
    """A wire-format tool call; pass a string to send arguments verbatim (even broken JSON)."""
    encoded = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {
        "id": call_id if call_id is not None else f"call_{next(_call_ids)}",
        "type": "function",
        "function": {"name": name, "arguments": encoded},
    }


def call_tools(*calls: dict[str, Any], content: str = "") -> dict[str, Any]:
    """An assistant turn requesting one or more tool calls."""
    return {"role": "assistant", "content": content, "tool_calls": list(calls)}


def answer(content: str, *, reasoning: str | None = None) -> dict[str, Any]:
    """An assistant turn without tool calls: the final answer."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return message


@dataclass
class ScriptedServer:
    """Replays ``replies`` in order and records every request body it receives."""

    replies: list[dict[str, Any]]
    prompt_tokens: int = 100
    completion_tokens: int = 10
    cached_tokens: int = 0
    delay_s: float = 0.0
    model_id: str = "fake-model"
    host: str = "fake"
    requests: list[dict[str, Any]] = field(default_factory=list)

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.host:
            raise httpx.ConnectError("connection refused", request=request)
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": self.model_id}]})
        if request.method != "POST" or request.url.path != "/v1/chat/completions":
            return httpx.Response(404, json={"error": {"message": "not found"}})

        body = json.loads(request.content)
        self.requests.append(body)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        index = len(self.requests) - 1
        if index >= len(self.replies):
            return httpx.Response(500, json={"error": {"message": "script exhausted"}})
        return httpx.Response(200, json=self._completion(index))

    def _completion(self, index: int) -> dict[str, Any]:
        message = self.replies[index]
        return {
            "id": f"chatcmpl-{index}",
            "object": "chat.completion",
            "model": self.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
                "prompt_tokens_details": {"cached_tokens": self.cached_tokens},
            },
        }

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport())

    def tool_messages(self, request_index: int = -1) -> list[dict[str, Any]]:
        """The ``role: "tool"`` messages sent with one request."""
        messages: list[dict[str, Any]] = self.requests[request_index]["messages"]
        return [m for m in messages if m["role"] == "tool"]
