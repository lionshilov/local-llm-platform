from __future__ import annotations

import asyncio
import json
import threading

import pytest
from llm_agent.messages import FunctionCall, ToolCall
from llm_agent.tools import ToolError, ToolErrorKind, ToolRegistry, tool
from pydantic import BaseModel


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    return a / b


@tool
def lookup(key: str) -> str:
    """Look up a key."""
    raise ToolError(f"no entry for '{key}'")


@tool
async def nap(seconds: float) -> str:
    """Sleep."""
    await asyncio.sleep(seconds)
    return "rested"


class Point(BaseModel):
    x: int
    y: int


@tool
def origin() -> Point:
    """Return the origin."""
    return Point(x=0, y=0)


def call(name: str, arguments: str) -> ToolCall:
    return ToolCall(id="call_1", function=FunctionCall(name=name, arguments=arguments))


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry([divide, lookup, nap, origin])


async def test_successful_call(registry: ToolRegistry) -> None:
    result = await registry.call(call("divide", '{"a": 1, "b": 4}'), timeout_s=1)
    assert result.ok
    assert result.output == "0.25"
    assert result.call_id == "call_1"
    assert result.latency_s >= 0


async def test_lax_coercion_and_double_encoded_arguments(registry: ToolRegistry) -> None:
    double_encoded = json.dumps(json.dumps({"a": "9", "b": 3}))
    result = await registry.call(call("divide", double_encoded), timeout_s=1)
    assert result.output == "3.0"


async def test_structured_return_values_are_serialized(registry: ToolRegistry) -> None:
    result = await registry.call(call("origin", ""), timeout_s=1)
    assert json.loads(result.output) == {"x": 0, "y": 0}


async def test_validation_errors_explain_the_fix(registry: ToolRegistry) -> None:
    result = await registry.call(call("divide", '{"a": "one", "c": 2}'), timeout_s=1)

    assert not result.ok
    assert result.error is ToolErrorKind.INVALID_ARGUMENTS
    assert result.output.startswith("Error: invalid arguments for 'divide': ")
    assert "a: Input should be a valid number" in result.output
    assert "b: Field required" in result.output
    assert "c: Extra inputs are not permitted" in result.output
    assert '"required":["a","b"]' in result.output  # the schema, to copy from


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ('{"a": 1, "b": ', "not valid JSON"),
        ("[1, 2]", "must be a JSON object, got list"),
    ],
)
async def test_malformed_arguments(registry: ToolRegistry, arguments: str, message: str) -> None:
    result = await registry.call(call("divide", arguments), timeout_s=1)
    assert result.error is ToolErrorKind.INVALID_ARGUMENTS
    assert message in result.output


async def test_unknown_tool_lists_the_available_ones(registry: ToolRegistry) -> None:
    result = await registry.call(call("multiply", "{}"), timeout_s=1)
    assert result.error is ToolErrorKind.UNKNOWN_TOOL
    assert "divide, lookup, nap, origin" in result.output


async def test_exceptions_become_error_results(registry: ToolRegistry) -> None:
    crashed = await registry.call(call("divide", '{"a": 1, "b": 0}'), timeout_s=1)
    explained = await registry.call(call("lookup", '{"key": "k"}'), timeout_s=1)

    assert crashed.error is ToolErrorKind.EXCEPTION
    assert crashed.output == "Error: ZeroDivisionError: float division by zero"
    assert explained.error is ToolErrorKind.TOOL_ERROR
    assert explained.output == "Error: no entry for 'k'"


async def test_timeout(registry: ToolRegistry) -> None:
    result = await registry.call(call("nap", '{"seconds": 5}'), timeout_s=0.05)
    assert result.error is ToolErrorKind.TIMEOUT
    assert result.output == "Error: 'nap' timed out after 0.05 s."
    assert result.latency_s < 2  # cancelled, not waiting for the 5 s nap


async def test_output_is_truncated() -> None:
    @tool
    def shout() -> str:
        """Be loud."""
        return "A" * 1000

    registry = ToolRegistry([shout], max_output_chars=200)
    result = await registry.call(call("shout", "{}"), timeout_s=1)
    assert result.output.startswith("A" * 200 + "\n[... truncated 800 characters]")


async def test_sync_tools_run_concurrently_in_worker_threads() -> None:
    barrier = threading.Barrier(3, timeout=5)  # breaks unless all three calls overlap

    @tool
    def blocking() -> str:
        """Block the calling thread."""
        barrier.wait()
        return threading.current_thread().name

    registry = ToolRegistry([blocking])
    results = await asyncio.gather(
        *(registry.call(call("blocking", "{}"), timeout_s=10) for _ in range(3))
    )
    assert all(r.ok for r in results), [r.output for r in results]
    assert threading.current_thread().name not in {r.output for r in results}


def test_duplicate_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate tool name 'divide'"):
        ToolRegistry([divide, divide])
