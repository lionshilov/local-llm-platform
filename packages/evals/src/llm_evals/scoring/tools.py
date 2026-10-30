"""Score single-turn function calling.

A reply passes when the model makes exactly the expected calls (any order) and nothing
else: right function names, arguments that validate against each tool's JSON Schema, and
every argument the request determines equal to the expected value (see ``matching``).
When no call is expected, any call fails.

Sub-checks separate the three ways to get it wrong: ``decision`` (call vs. answer in text),
``function`` (which tools) and ``arguments`` (what was passed).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import permutations
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from llm_evals.reply import ToolCall
from llm_evals.scoring import Score
from llm_evals.scoring.matching import mismatch
from llm_evals.scoring.validation import schema_errors


class ToolSpec(BaseModel):
    """A function the model may call, in OpenAI's ``tools`` format."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    parameters: dict[str, Any] = Field(description="JSON Schema of the arguments object.")

    def to_openai(self) -> dict[str, Any]:
        return {"type": "function", "function": self.model_dump()}


class ExpectedCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    arguments: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Arguments the request determines; may use matchers such as $any_of.",
    )


def _parse_arguments(call: ToolCall) -> dict[str, JsonValue] | str:
    try:
        arguments = json.loads(call.arguments or "{}")
    except ValueError:
        return f"{call.name}: arguments are not valid JSON: {call.arguments[:80]!r}"
    if not isinstance(arguments, dict):
        return f"{call.name}: arguments must be a JSON object, got {call.arguments[:80]!r}"
    return arguments


def _argument_problem(
    expected: ExpectedCall, arguments: dict[str, JsonValue], tools: Mapping[str, ToolSpec]
) -> str | None:
    if expected.name in tools and (
        errors := schema_errors(arguments, tools[expected.name].parameters)
    ):
        return f"{expected.name}: schema violation at {errors[0]}"
    if problem := mismatch(dict(expected.arguments), dict(arguments)):
        return f"{expected.name}: {problem}"
    return None


def score_tool_calls(
    expected: Sequence[ExpectedCall], calls: Sequence[ToolCall], tools: Mapping[str, ToolSpec]
) -> Score:
    called = [call.name for call in calls]
    extracted: JsonValue = [{"name": c.name, "arguments": c.arguments} for c in calls]

    if not expected:
        if called:
            return Score(
                passed=False,
                extracted=extracted,
                reason=f"expected no tool call, got {', '.join(called)}",
                checks={"decision": False},
            )
        return Score(passed=True, checks={"decision": True})

    wanted = [call.name for call in expected]
    checks = {"decision": bool(calls), "function": False, "arguments": False}
    if not calls:
        return Score(
            passed=False,
            reason=f"expected {', '.join(wanted)}, got a text answer",
            checks=checks,
        )
    if Counter(called) != Counter(wanted):
        return Score(
            passed=False,
            extracted=extracted,
            reason=f"expected {', '.join(wanted)}, got {', '.join(called)}",
            checks=checks,
        )
    checks["function"] = True

    parsed: list[dict[str, JsonValue]] = []
    for call in calls:
        arguments = _parse_arguments(call)
        if isinstance(arguments, str):
            return Score(passed=False, extracted=extracted, reason=arguments, checks=checks)
        parsed.append(arguments)
    extracted = [{"name": c.name, "arguments": a} for c, a in zip(calls, parsed, strict=True)]

    first_problem: str | None = None
    for order in permutations(range(len(calls))):
        pairs = [(expected[i], calls[j], parsed[j]) for i, j in enumerate(order)]
        if any(exp.name != call.name for exp, call, _ in pairs):
            continue
        problems = [_argument_problem(exp, args, tools) for exp, _, args in pairs]
        if not any(problems):
            checks["arguments"] = True
            return Score(passed=True, extracted=extracted, checks=checks)
        first_problem = first_problem or next(p for p in problems if p)
    return Score(passed=False, extracted=extracted, reason=first_problem, checks=checks)
