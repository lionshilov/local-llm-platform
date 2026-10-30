"""Non-streaming Chat Completions client on raw httpx, no SDK.

One request per agent step. Anything that is not a well-formed completion becomes a
``ModelError`` so the agent loop has a single failure type to handle.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from llm_agent.config import ClientConfig
from llm_agent.messages import Message, ToolCall, Usage


class ModelError(Exception):
    """The endpoint failed or returned something that is not a chat completion."""


class Completion(BaseModel):
    message: Message
    reasoning: str | None = Field(default=None, description="Thinking text, if the model sent any.")
    usage: Usage
    finish_reason: str | None = None
    latency_s: float
    server_timings: dict[str, Any] | None = Field(
        default=None, description="Server-side compute timings (llama.cpp's `timings`)."
    )


class _WireMessage(BaseModel):
    content: str | None = None
    # llama.cpp says reasoning_content; Ollama and MLX-LM say reasoning.
    reasoning_content: str | None = None
    reasoning: str | None = None
    tool_calls: list[ToolCall] | None = None


class _WireChoice(BaseModel):
    message: _WireMessage
    finish_reason: str | None = None


class _WireResponse(BaseModel):
    choices: list[_WireChoice] = Field(min_length=1)
    usage: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None


def parse_completion(payload: Any, latency_s: float) -> Completion:
    if isinstance(payload, dict) and "error" in payload:
        raise ModelError(f"server error: {payload['error']}")
    try:
        response = _WireResponse.model_validate(payload)
    except ValidationError as exc:
        raise ModelError(f"not a chat completion: {exc.error_count()} validation error(s)") from exc

    choice = response.choices[0]
    wire = choice.message
    message = Message(
        role="assistant",
        content=wire.content or "",
        tool_calls=wire.tool_calls or None,
    )
    return Completion(
        message=message,
        reasoning=wire.reasoning_content or wire.reasoning or None,
        usage=Usage.from_wire(response.usage),
        finish_reason=choice.finish_reason,
        latency_s=latency_s,
        server_timings=response.timings,
    )


class ChatClient:
    def __init__(self, config: ClientConfig, http: httpx.AsyncClient) -> None:
        self.config = config
        self.http = http

    def build_body(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.to_wire() for message in messages],
        }
        if tools:
            body["tools"] = list(tools)
        return {**body, **self.config.request_fields()}

    async def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]] = ()
    ) -> Completion:
        headers = {}
        if self.config.api_key is not None:
            headers["Authorization"] = f"Bearer {self.config.api_key.get_secret_value()}"

        started = time.perf_counter()
        try:
            response = await self.http.post(
                f"{self.config.base_url}/chat/completions",
                json=self.build_body(messages, tools),
                headers=headers,
                timeout=self.config.timeout_s,
            )
        except httpx.HTTPError as exc:
            raise ModelError(f"{type(exc).__name__}: {exc}") from exc
        latency_s = time.perf_counter() - started

        if response.status_code != httpx.codes.OK:
            raise ModelError(f"HTTP {response.status_code}: {response.text[:300]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelError(f"response is not JSON: {response.text[:200]}") from exc
        return parse_completion(payload, latency_s)
