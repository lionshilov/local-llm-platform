"""A scripted in-process OpenAI-compatible server for tests (built on ``httpx.MockTransport``).

Unlike llm-bench's ``FakeServer``, which streams filler tokens, this one answers each
request with a reply chosen by a script, so tests can make a model right, wrong, slow,
broken, or call tools.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class Scripted:
    """One canned reply. ``status`` other than 200 returns an OpenAI-style error body."""

    content: str = ""
    reasoning: str | None = None
    tool_calls: list[tuple[str, dict[str, Any] | str]] = field(default_factory=list)
    finish_reason: str | None = None
    status: int = 200
    delay_s: float = 0.0


Script = Callable[[dict[str, Any]], Scripted | str]


def last_user_message(body: Mapping[str, Any]) -> str:
    users = [m.get("content", "") for m in body.get("messages", []) if m.get("role") == "user"]
    return str(users[-1]) if users else ""


def by_prompt(replies: Mapping[str, Scripted | str], default: Scripted | str = "") -> Script:
    """Answer with the first entry whose key occurs in the last user message."""

    def script(body: dict[str, Any]) -> Scripted | str:
        prompt = last_user_message(body)
        return next((reply for key, reply in replies.items() if key in prompt), default)

    return script


def _silent(_: dict[str, Any]) -> Scripted | str:
    return ""


@dataclass
class ScriptedServer:
    script: Script = _silent
    model_id: str = "fake-model"
    host: str = "fake"
    connect_failures: int = 0
    requests: list[dict[str, Any]] = field(default_factory=list)
    in_flight: int = 0
    peak_in_flight: int = 0

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.host:
            raise httpx.ConnectError("connection refused", request=request)
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": self.model_id}]})
        if request.method == "POST" and request.url.path == "/v1/chat/completions":
            if self.connect_failures > 0:
                self.connect_failures -= 1
                raise httpx.ConnectError("connection reset", request=request)
            body = json.loads(request.content)
            self.requests.append(body)
            reply = self.script(body)
            if isinstance(reply, str):
                reply = Scripted(content=reply)
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
            try:
                await asyncio.sleep(reply.delay_s)  # also yields, so requests can overlap
            finally:
                self.in_flight -= 1
            if reply.status != httpx.codes.OK:
                error = {"error": {"message": "scripted failure", "code": reply.status}}
                return httpx.Response(reply.status, json=error)
            return httpx.Response(200, json=self._completion(body, reply))
        return httpx.Response(404, json={"error": {"message": "not found"}})

    def _completion(self, body: dict[str, Any], reply: Scripted) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": reply.content}
        if reply.reasoning is not None:
            message["reasoning_content"] = reply.reasoning
        if reply.tool_calls:
            message["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args if isinstance(args, str) else json.dumps(args),
                    },
                }
                for i, (name, args) in enumerate(reply.tool_calls)
            ]
        finish = reply.finish_reason or ("tool_calls" if reply.tool_calls else "stop")
        generated = f"{reply.reasoning or ''} {reply.content}".split()
        return {
            "object": "chat.completion",
            "model": self.model_id,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": len(last_user_message(body).split()),
                "completion_tokens": len(generated) + 10 * len(reply.tool_calls),
            },
        }

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport())
