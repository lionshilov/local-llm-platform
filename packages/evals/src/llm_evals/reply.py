"""What a model returned for one request, normalized across OpenAI-compatible servers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: str = Field(description="Raw JSON string, exactly as the server sent it.")


class Reply(BaseModel):
    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @classmethod
    def from_openai(cls, payload: dict[str, Any]) -> Reply:
        """Parse a non-streaming ``chat.completion`` response body."""
        choices = payload.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}
        usage = payload.get("usage") or {}

        content = message.get("content") or ""
        # llama.cpp says reasoning_content, Ollama and MLX say reasoning; servers without a
        # reasoning parser leave <think>...</think> inline in the content.
        reasoning = message.get("reasoning_content") or message.get("reasoning") or None
        if "</think>" in content:
            inline, content = content.rsplit("</think>", 1)
            reasoning = reasoning or inline.replace("<think>", "").strip()

        return cls(
            content=content.strip(),
            reasoning=reasoning,
            tool_calls=[_tool_call(raw) for raw in message.get("tool_calls") or []],
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )


def _tool_call(raw: dict[str, Any]) -> ToolCall:
    function = raw.get("function") or {}
    arguments = function.get("arguments", "")
    if not isinstance(arguments, str):  # some servers send an already-decoded object
        arguments = json.dumps(arguments)
    return ToolCall(name=function.get("name", ""), arguments=arguments)
