"""Chat Completions wire types: messages, tool calls and token usage."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator

Role = Literal["system", "user", "assistant", "tool"]


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


class FunctionCall(BaseModel):
    name: str
    arguments: str = Field(description="JSON-encoded arguments exactly as the model wrote them.")

    @field_validator("arguments", mode="before")
    @classmethod
    def _encode_object(cls, value: Any) -> Any:
        # The spec says string, but some servers (and Ollama's native API) send an object.
        if isinstance(value, dict):
            return json.dumps(value)
        return "" if value is None else value


class ToolCall(BaseModel):
    id: str = Field(default_factory=new_call_id)
    type: Literal["function"] = "function"
    function: FunctionCall

    @field_validator("id", mode="before")
    @classmethod
    def _ensure_id(cls, value: Any) -> Any:
        # Older servers omit ids; tool results must still be matched to their call.
        return value or new_call_id()


class Message(BaseModel):
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    @classmethod
    def system(cls, content: str) -> Self:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Self:
        return cls(role="user", content=content)

    @classmethod
    def tool(cls, call_id: str, content: str) -> Self:
        return cls(role="tool", tool_call_id=call_id, content=content)

    def to_wire(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Usage(BaseModel):
    """Token counts as reported by the server's ``usage`` block."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = Field(
        default=0, description="Prompt tokens served from the server's KV (prefix) cache."
    )

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
        )

    @classmethod
    def from_wire(cls, usage: dict[str, Any] | None) -> Usage:
        if not usage:
            return cls()
        details = usage.get("prompt_tokens_details") or {}
        return cls(
            prompt_tokens=usage.get("prompt_tokens") or 0,
            completion_tokens=usage.get("completion_tokens") or 0,
            cached_tokens=details.get("cached_tokens") or 0,
        )
