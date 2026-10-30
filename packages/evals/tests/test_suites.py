"""The shipped suites are data, so they get tested like code.

Every item carries (or implies) a reference answer that must pass its own scorer: this is
what catches a wrong answer key, an unsatisfiable schema or contradictory instructions
before a model is ever blamed for them.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest
from llm_evals.reply import Reply, ToolCall
from llm_evals.scoring.matching import example_of
from llm_evals.scoring.validation import schema_errors
from llm_evals.suite import (
    SUITE_NAMES,
    ChoiceSuite,
    InstructionsSuite,
    JsonSuite,
    MathSuite,
    ToolsSuite,
    load_suite,
    load_suites,
    parse_suite,
)
from llm_evals.tasks import tasks_for
from pydantic import ValidationError

SUITES = load_suites()


def test_every_suite_ships_and_has_a_usable_size() -> None:
    assert tuple(SUITES) == SUITE_NAMES
    for suite in SUITES.values():
        assert 20 <= len(suite.items) <= 40, suite.name


def test_item_ids_are_unique_across_suites() -> None:
    ids = Counter(item.id for suite in SUITES.values() for item in suite.items)
    assert [i for i, count in ids.items() if count > 1] == []


def test_fingerprint_is_stable_and_content_sensitive() -> None:
    math = load_suite("math")
    assert math.fingerprint == parse_suite(math.model_dump_json()).fingerprint
    changed = math.model_copy(update={"items": math.items[:-1]})
    assert changed.fingerprint != math.fingerprint


def test_math_answers_are_reachable() -> None:
    suite = SUITES["math"]
    assert isinstance(suite, MathSuite)
    [task] = tasks_for(suite)
    for item in suite.items:
        reply = Reply(content=f"Some working.\nAnswer: {item.answer:g}")
        assert task.score(item, reply).passed, item.id


def test_choice_answers_are_balanced() -> None:
    suite = SUITES["reasoning"]
    assert isinstance(suite, ChoiceSuite)
    [task] = tasks_for(suite)
    for item in suite.items:
        assert task.score(item, Reply(content=f"Answer: {item.answer}")).passed, item.id
    counts = Counter(item.answer for item in suite.items)
    assert max(counts.values()) / len(suite.items) <= 0.35  # no letter is a free win


def test_json_references_pass_in_both_modes() -> None:
    suite = SUITES["json"]
    assert isinstance(suite, JsonSuite)
    prompted, constrained = tasks_for(suite)
    assert (prompted.name, constrained.name) == ("json/prompted", "json/constrained")
    for item in suite.items:
        reply = Reply(content=json.dumps(item.reference))
        assert prompted.score(item, reply).passed, item.id
        assert constrained.score(item, reply).passed, item.id


def test_tool_references_pass_and_respect_the_tool_schemas() -> None:
    suite = SUITES["tools"]
    assert isinstance(suite, ToolsSuite)
    [task] = tasks_for(suite)
    schemas = {tool.name: tool.parameters for tool in suite.tools}
    no_call = 0
    for item in suite.items:
        calls = [
            ToolCall(name=call.name, arguments=json.dumps(example_of(call.arguments)))
            for call in item.calls
        ]
        for call in item.calls:
            assert schema_errors(example_of(call.arguments), schemas[call.name]) == [], item.id
        assert task.score(item, Reply(tool_calls=calls)).passed, item.id
        no_call += not item.calls
    assert no_call >= 5, "the suite must test when *not* to call a tool"


def test_instruction_references_pass() -> None:
    suite = SUITES["instructions"]
    assert isinstance(suite, InstructionsSuite)
    [task] = tasks_for(suite)
    for item in suite.items:
        assert item.reference is not None, item.id
        score = task.score(item, Reply(content=item.reference))
        assert score.passed, f"{item.id}: {score.reason}"
    per_type = Counter(i.type for item in suite.items for i in item.instructions)
    assert min(per_type.values()) >= 3, per_type


def test_requests_are_well_formed() -> None:
    for suite in SUITES.values():
        for task in tasks_for(suite):
            request = task.request(task.items[0])
            assert request.prompt
            assert request.messages[-1]["role"] == "user"
            assert (request.tools is not None) == (suite.kind == "tools")
            assert (request.response_format is not None) == (task.name == "json/constrained")


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            "name: x\nkind: math\ndescription: d\nitems:\n"
            "  - {id: a, question: q, answer: 1}\n  - {id: a, question: q, answer: 2}",
            "duplicate item ids: a",
        ),
        (
            "name: x\nkind: choice\ndescription: d\nitems:\n"
            "  - {id: a, question: q, options: [x, y], answer: C}",
            "answer C is not one of the 2 options",
        ),
        (
            "name: x\nkind: json\ndescription: d\nitems:\n"
            "  - {id: a, task: t, json_schema: {type: nope}, reference: {}}",
            "invalid JSON Schema",
        ),
        (
            "name: x\nkind: tools\ndescription: d\n"
            "tools: [{name: f, description: d, parameters: {type: object}}]\nitems:\n"
            "  - {id: a, prompt: p, calls: [{name: g}]}",
            "unknown tool(s) g",
        ),
        (
            "name: x\nkind: instructions\ndescription: d\nitems:\n"
            "  - {id: a, task: t, instructions: [{type: lowercase}, {type: lowercase}]}",
            "an instruction type appears twice",
        ),
        ("name: x\nkind: poetry\ndescription: d\nitems: []", "does not match any of the expected"),
    ],
)
def test_malformed_suites_are_rejected(document: str, message: str) -> None:
    with pytest.raises(ValidationError, match=re.escape(message)):
        parse_suite(document)


def test_unknown_suite_name() -> None:
    with pytest.raises(KeyError, match="unknown suite"):
        load_suite("poetry")
