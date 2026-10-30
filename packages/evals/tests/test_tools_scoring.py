from __future__ import annotations

import json
from typing import Any

import pytest
from llm_evals.reply import ToolCall
from llm_evals.scoring.tools import ExpectedCall, ToolSpec, score_tool_calls

TOOLS = {
    "get_weather": ToolSpec(
        name="get_weather",
        description="Weather in a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
            "additionalProperties": False,
        },
    ),
    "set_timer": ToolSpec(
        name="set_timer",
        description="Start a timer.",
        parameters={
            "type": "object",
            "properties": {"duration_seconds": {"type": "integer", "minimum": 1}},
            "required": ["duration_seconds"],
            "additionalProperties": False,
        },
    ),
}
WEATHER_ROME = ExpectedCall(name="get_weather", arguments={"city": "Rome"})


def call(name: str, arguments: dict[str, Any] | str) -> ToolCall:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return ToolCall(name=name, arguments=raw)


def test_correct_call_with_normalized_arguments() -> None:
    score = score_tool_calls([WEATHER_ROME], [call("get_weather", {"city": " rome "})], TOOLS)
    assert score.passed
    assert score.checks == {"decision": True, "function": True, "arguments": True}
    assert score.extracted == [{"name": "get_weather", "arguments": {"city": " rome "}}]


def test_optional_arguments_the_request_did_not_fix_are_allowed() -> None:
    calls = [call("get_weather", {"city": "Rome", "unit": "celsius"})]
    assert score_tool_calls([WEATHER_ROME], calls, TOOLS).passed


def test_numbers_compare_by_value() -> None:
    expected = [ExpectedCall(name="set_timer", arguments={"duration_seconds": 600})]
    assert score_tool_calls(
        expected, [call("set_timer", '{"duration_seconds": 600}')], TOOLS
    ).passed
    wrong = score_tool_calls(expected, [call("set_timer", {"duration_seconds": 60})], TOOLS)
    assert wrong.reason == "set_timer: /duration_seconds: expected 600, got 60"
    assert wrong.checks == {"decision": True, "function": True, "arguments": False}


def test_parallel_calls_in_any_order() -> None:
    expected = [WEATHER_ROME, ExpectedCall(name="get_weather", arguments={"city": "Madrid"})]
    calls = [call("get_weather", {"city": "Madrid"}), call("get_weather", {"city": "Rome"})]
    assert score_tool_calls(expected, calls, TOOLS).passed


@pytest.mark.parametrize(
    ("calls", "reason", "checks"),
    [
        ([], "expected get_weather, got a text answer", {"decision": False}),
        ([call("set_timer", {"duration_seconds": 5})], "expected get_weather, got set_timer", {}),
        (
            [call("get_weather", {"city": "Rome"})] * 2,
            "expected get_weather, got get_weather, get_weather",
            {"function": False},
        ),
        (
            [call("get_weather", "{city: Rome}")],
            "get_weather: arguments are not valid JSON",
            {"function": True, "arguments": False},
        ),
        ([call("get_weather", "[1]")], "get_weather: arguments must be a JSON object", {}),
        (
            [call("get_weather", {"city": "Rome", "unit": "kelvin"})],
            "get_weather: schema violation at /unit: 'kelvin' is not one of",
            {"function": True, "arguments": False},
        ),
        (
            [call("get_weather", {"city": "Rome", "country": "IT"})],
            "get_weather: schema violation at /: Additional properties are not allowed",
            {},
        ),
        ([call("get_weather", {"city": "Milan"})], "get_weather: /city: expected 'Rome'", {}),
    ],
)
def test_wrong_calls(calls: list[ToolCall], reason: str, checks: dict[str, bool]) -> None:
    score = score_tool_calls([WEATHER_ROME], calls, TOOLS)
    assert not score.passed
    assert score.reason is not None
    assert score.reason.startswith(reason)
    assert checks.items() <= score.checks.items()


def test_should_not_call() -> None:
    assert score_tool_calls([], [], TOOLS).checks == {"decision": True}

    called = score_tool_calls([], [call("get_weather", {"city": "Paris"})], TOOLS)
    assert not called.passed
    assert called.reason == "expected no tool call, got get_weather"
    assert called.checks == {"decision": False}
    assert called.extracted == [{"name": "get_weather", "arguments": '{"city": "Paris"}'}]


def test_openai_tool_format() -> None:
    assert TOOLS["set_timer"].to_openai() == {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Start a timer.",
            "parameters": TOOLS["set_timer"].parameters,
        },
    }
