"""Look up, validate and execute tool calls. Every failure becomes a result, never an exception.

The model sees exactly what went wrong ("unknown tool", "invalid arguments: ...", "timed
out") in the tool message, which is what lets it correct itself on the next step.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable, Iterator
from enum import StrEnum
from typing import Any

import pydantic_core
from pydantic import BaseModel, Field

from llm_agent.messages import ToolCall
from llm_agent.tools.base import AnyTool, InvalidArgumentsError, ToolError


class ToolErrorKind(StrEnum):
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"  # the tool raised ToolError: an expected, explained failure
    EXCEPTION = "exception"  # anything else the tool raised


class ToolResult(BaseModel):
    call_id: str
    name: str
    ok: bool
    output: str = Field(description="Text returned to the model, error messages included.")
    error: ToolErrorKind | None = None
    latency_s: float = 0.0


def to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return pydantic_core.to_json(value, fallback=str).decode()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[... truncated {len(text) - limit:,} characters]"


class ToolRegistry:
    def __init__(self, tools: Iterable[AnyTool] = (), *, max_output_chars: int = 8000) -> None:
        self.max_output_chars = max_output_chars
        self._tools: dict[str, AnyTool] = {}
        for item in tools:
            self.add(item)

    def add(self, tool: AnyTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name '{tool.name}'")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AnyTool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def __iter__(self) -> Iterator[AnyTool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    async def call(self, call: ToolCall, *, timeout_s: float) -> ToolResult:
        """Execute one tool call within ``timeout_s`` seconds."""
        started = time.perf_counter()
        name = call.function.name

        def result(output: str, error: ToolErrorKind | None = None) -> ToolResult:
            return ToolResult(
                call_id=call.id,
                name=name,
                ok=error is None,
                output=truncate(output, self.max_output_chars),
                error=error,
                latency_s=time.perf_counter() - started,
            )

        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self._tools) or "none"
            return result(
                f"Error: unknown tool '{name}'. Available tools: {available}.",
                ToolErrorKind.UNKNOWN_TOOL,
            )
        try:
            arguments = tool.parse_arguments(call.function.arguments)
        except InvalidArgumentsError as exc:
            return result(f"Error: {exc}", ToolErrorKind.INVALID_ARGUMENTS)

        deadline = asyncio.timeout(timeout_s)
        try:
            async with deadline:
                output = await tool.invoke(arguments)
        except TimeoutError as exc:
            if deadline.expired():
                return result(
                    f"Error: '{name}' timed out after {timeout_s:g} s.", ToolErrorKind.TIMEOUT
                )
            return result(f"Error: TimeoutError: {exc}", ToolErrorKind.EXCEPTION)
        except ToolError as exc:
            return result(f"Error: {exc}", ToolErrorKind.TOOL_ERROR)
        except Exception as exc:
            return result(f"Error: {type(exc).__name__}: {exc}", ToolErrorKind.EXCEPTION)
        return result(to_text(output))
