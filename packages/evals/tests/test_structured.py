from __future__ import annotations

from typing import Any

import pytest
from llm_evals.scoring.structured import parse_json, score_json
from pydantic import JsonValue

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
    },
    "required": ["name", "age"],
    "additionalProperties": False,
}


def test_valid_and_correct() -> None:
    score = score_json('{"name": "Tom", "age": 3}', SCHEMA, {"/name": "tom", "/age": 3})
    assert score.passed
    assert score.extracted == {"name": "Tom", "age": 3}
    assert score.checks == {"valid_json": True, "schema_valid": True, "values_correct": True}


def test_single_code_fence_is_unwrapped() -> None:
    assert score_json('```json\n{"name": "Tom", "age": 3}\n```', SCHEMA).passed
    assert parse_json('```\n{"a": 1}```') == {"a": 1}


@pytest.mark.parametrize(
    "text",
    [
        'Here you go: {"name": "Tom", "age": 3}',  # prose around the JSON
        '{"name": "Tom", "age": 3',  # truncated
        "{'name': 'Tom', 'age': 3}",  # Python, not JSON
        '{"name": "Tom", "age": NaN}',  # Python's json would accept this
        "",
    ],
)
def test_invalid_json(text: str) -> None:
    score = score_json(text, SCHEMA)
    assert not score.passed
    assert score.reason is not None
    assert score.reason.startswith("not valid JSON")
    assert score.checks == {"valid_json": False, "schema_valid": False}


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ('{"name": "Tom"}', "/: 'age' is a required property"),
        ('{"name": "Tom", "age": "3"}', "/age: '3' is not of type 'integer'"),
        ('{"name": "Tom", "age": -1}', "/age: -1 is less than the minimum of 0"),
        ('{"name": "Tom", "age": 3, "x": 1}', "/: Additional properties are not allowed"),
        (
            '{"name": "Tom", "age": 3, "tags": ["a", "b", "c"]}',
            "/tags: ['a', 'b', 'c'] is too long",
        ),
        ("[1, 2]", "/: [1, 2] is not of type 'object'"),
    ],
)
def test_schema_violations(text: str, where: str) -> None:
    score = score_json(text, SCHEMA)
    assert not score.passed
    assert score.reason is not None
    assert score.reason.startswith(f"schema violation at {where}")
    assert score.checks == {"valid_json": True, "schema_valid": False}


def test_schema_valid_but_wrong_values() -> None:
    expected: dict[str, JsonValue] = {"/name": "Tom", "/age": 3}
    wrong = score_json('{"name": "Tom", "age": 4}', SCHEMA, expected)
    assert not wrong.passed
    assert wrong.reason == "/age: expected 3, got 4"
    assert wrong.checks == {"valid_json": True, "schema_valid": True, "values_correct": False}

    missing = score_json('{"name": "Tom", "age": 3}', SCHEMA, {"/tags/0": "a"})
    assert missing.reason == "/tags/0: missing"


def test_multiple_violations_are_counted() -> None:
    score = score_json('{"age": "x", "extra": true}', SCHEMA)
    assert score.reason is not None
    assert "(+2 more)" in score.reason
