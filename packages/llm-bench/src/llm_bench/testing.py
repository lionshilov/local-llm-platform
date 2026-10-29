"""An in-process fake OpenAI-compatible server for tests (built on ``httpx.MockTransport``)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class FakeServer:
    """Streams ``tokens`` chunks per request and records every request body it receives."""

    tokens: int = 5
    text_field: str = "content"
    send_usage: bool = True
    first_token_delay_s: float = 0.0
    prompt_tokens: int = 42
    model_id: str = "fake-model"
    host: str = "fake"
    requests: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _sse(payload: dict[str, Any]) -> bytes:
        return f"data: {json.dumps(payload)}\n\n".encode()

    async def _stream(self) -> AsyncIterator[bytes]:
        yield b": keep-alive\n\n"
        if self.first_token_delay_s:
            await asyncio.sleep(self.first_token_delay_s)
        for i in range(self.tokens):
            finish = "length" if i == self.tokens - 1 else None
            delta = {self.text_field: f"tok{i} "}
            yield self._sse({"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]})
        if self.send_usage:
            usage = {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.tokens}
            yield self._sse({"choices": [], "usage": usage})
        yield b"data: [DONE]\n\n"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.host:
            raise httpx.ConnectError("connection refused", request=request)
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": self.model_id}]})
        if request.method == "POST" and request.url.path == "/v1/chat/completions":
            body = json.loads(request.content)
            self.requests.append(body)
            if not body.get("stream"):
                return httpx.Response(200, json=self._completion())
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=self._stream()
            )
        return httpx.Response(404, json={"error": "not found"})

    def _completion(self) -> dict[str, Any]:
        text = "".join(f"tok{i} " for i in range(self.tokens))
        return {
            "object": "chat.completion",
            "model": self.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", self.text_field: text},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.tokens},
        }

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport())
