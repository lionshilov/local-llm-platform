from __future__ import annotations

import asyncio
import itertools
from pathlib import Path
from typing import Any

import pytest
from llm_agent import Agent, AgentLimits, ClientConfig, JsonlTrace, RunStatus, read_trace, tool
from llm_agent.events import Event, ToolReturned
from llm_agent.testing import ScriptedServer, answer, call_tools, tool_call
from llm_agent.tools import AnyTool, ToolErrorKind, calculator


def make_agent(
    server: ScriptedServer, config: ClientConfig, *tools: AnyTool, **limits: Any
) -> Agent:
    return Agent(
        config, [calculator, *tools], limits=AgentLimits(**limits), http_client=server.client()
    )


async def test_tool_results_go_back_to_the_model(config: ClientConfig) -> None:
    server = ScriptedServer(
        [
            call_tools(tool_call("calculator", {"expression": "6 * 7"}, call_id="c1")),
            answer("6 * 7 = 42", reasoning="easy"),
        ]
    )
    result = await make_agent(server, config).run("What is 6 * 7?")

    assert result.status is RunStatus.COMPLETED
    assert result.ok
    assert result.answer == "6 * 7 = 42"
    assert [len(step.tool_calls) for step in result.steps] == [1, 0]
    assert result.steps[1].reasoning == "easy"
    assert result.usage.prompt_tokens == 200
    assert result.usage.completion_tokens == 20

    first, second = server.requests
    assert first["model"] == "fake-model"
    assert [m["role"] for m in first["messages"]] == ["system", "user"]
    assert first["tools"][0]["function"]["name"] == "calculator"
    assert [m["role"] for m in second["messages"]] == ["system", "user", "assistant", "tool"]
    assert second["messages"][2]["tool_calls"][0]["id"] == "c1"
    assert server.tool_messages() == [{"role": "tool", "tool_call_id": "c1", "content": "42"}]


async def test_parallel_tool_calls_run_concurrently(config: ClientConfig) -> None:
    barrier = asyncio.Barrier(2)

    @tool
    async def fetch(key: str, delay: float) -> str:
        """Fetch a value."""
        async with asyncio.timeout(1):
            await barrier.wait()  # only passes if both calls are in flight at once
        await asyncio.sleep(delay)
        return f"value of {key}"

    server = ScriptedServer(
        [
            call_tools(
                tool_call("fetch", {"key": "a", "delay": 0.05}, call_id="a"),
                tool_call("fetch", {"key": "b", "delay": 0}, call_id="b"),
            ),
            answer("done"),
        ]
    )
    events: list[Event] = []
    agent = Agent(config, [fetch], http_client=server.client(), on_event=[events.append])
    result = await agent.run("fetch a and b")

    assert result.ok
    # Results go back in call order, although "b" finished first.
    assert server.tool_messages() == [
        {"role": "tool", "tool_call_id": "a", "content": "value of a"},
        {"role": "tool", "tool_call_id": "b", "content": "value of b"},
    ]
    finished = [e.call_id for e in events if isinstance(e, ToolReturned)]
    assert finished == ["b", "a"]


async def test_model_recovers_from_bad_arguments(config: ClientConfig) -> None:
    server = ScriptedServer(
        [
            call_tools(tool_call("calculator", '{"expression": "2+2"')),
            call_tools(tool_call("calculator", {"expr": "2+2"})),
            call_tools(tool_call("calculator", {"expression": "2+2"})),
            answer("4"),
        ]
    )
    result = await make_agent(server, config).run("2+2?")

    assert result.ok
    errors = [step.tool_results[0].error for step in result.steps[:3]]
    assert errors == [ToolErrorKind.INVALID_ARGUMENTS, ToolErrorKind.INVALID_ARGUMENTS, None]
    assert "not valid JSON" in server.tool_messages(1)[0]["content"]
    assert "expression: Field required" in server.tool_messages(2)[-1]["content"]


async def test_tool_exceptions_and_timeouts_do_not_end_the_run(config: ClientConfig) -> None:
    @tool
    def broken() -> str:
        """Always fails."""
        raise RuntimeError("disk on fire")

    @tool
    async def slow() -> str:
        """Takes forever."""
        await asyncio.sleep(10)
        return "never"

    server = ScriptedServer(
        [
            call_tools(tool_call("broken", {}), tool_call("slow", {}), tool_call("nope", {})),
            answer("Both tools failed."),
        ]
    )
    result = await make_agent(server, config, broken, slow, tool_timeout_s=0.05).run("try")

    assert result.ok
    assert [r.error for r in result.steps[0].tool_results] == [
        ToolErrorKind.EXCEPTION,
        ToolErrorKind.TIMEOUT,
        ToolErrorKind.UNKNOWN_TOOL,
    ]
    assert server.tool_messages()[0]["content"] == "Error: RuntimeError: disk on fire"


async def test_max_steps(config: ClientConfig) -> None:
    loop = [call_tools(tool_call("calculator", {"expression": "1+1"})) for _ in range(5)]
    server = ScriptedServer(loop)
    result = await make_agent(server, config, max_steps=3).run("loop forever")

    assert result.status is RunStatus.MAX_STEPS
    assert result.answer is None
    assert result.error == "no final answer after 3 steps"
    assert len(server.requests) == 3
    assert result.tool_calls == 3


async def test_time_budget(config: ClientConfig) -> None:
    server = ScriptedServer([answer("too late")], delay_s=5)
    result = await make_agent(server, config, time_budget_s=0.05).run("hurry")

    assert result.status is RunStatus.TIME_BUDGET
    assert result.elapsed_s < 2  # cancelled, not waiting for the 5 s reply
    assert result.steps == []


@pytest.mark.parametrize(
    ("replies", "status", "error"),
    [
        ([], RunStatus.MODEL_ERROR, "HTTP 500"),
        ([answer("  ")], RunStatus.NO_ANSWER, "neither tool calls nor an answer"),
    ],
)
async def test_failures(
    config: ClientConfig, replies: list[dict[str, object]], status: RunStatus, error: str
) -> None:
    result = await make_agent(ScriptedServer(replies), config).run("hi")

    assert result.status is status
    assert not result.ok
    assert result.answer is None
    assert result.error is not None
    assert error in result.error


async def test_request_fields(config: ClientConfig) -> None:
    config = config.model_copy(
        update={"extra_body": {"top_k": 20, "chat_template_kwargs": {"foo": 1}}}
    )
    server = ScriptedServer([answer("hi")])
    await Agent(config, http_client=server.client(), system_prompt="Be brief.").run("hi")

    body = server.requests[0]
    assert "tools" not in body
    assert body["messages"][0] == {"role": "system", "content": "Be brief."}
    assert body["temperature"] == 0.0
    assert body["top_k"] == 20
    assert body["reasoning_effort"] == "none"
    assert body["chat_template_kwargs"] == {"enable_thinking": False, "foo": 1}


async def test_trace_is_written_as_jsonl(config: ClientConfig, tmp_path: Path) -> None:
    server = ScriptedServer(
        [call_tools(tool_call("calculator", {"expression": "1/0"})), answer("undefined")]
    )
    path = tmp_path / "traces" / "run.jsonl"
    with JsonlTrace(path) as trace:
        agent = Agent(config, [calculator], http_client=server.client(), on_event=[trace])
        result = await agent.run("1/0?")

    events = read_trace(path)
    assert [e.type for e in events] == [
        "run_started",
        "model_call",
        "tool_call",
        "tool_result",
        "model_call",
        "final_answer",
        "run_finished",
    ]
    assert {e.run_id for e in events} == {result.run_id}
    assert all(a.elapsed_s <= b.elapsed_s for a, b in itertools.pairwise(events))
    tool_result = events[3]
    assert isinstance(tool_result, ToolReturned)
    assert tool_result.output == "Error: division by zero"
