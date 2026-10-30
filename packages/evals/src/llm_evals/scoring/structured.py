"""Score structured output: valid JSON, valid against a JSON Schema, and the right facts.

A schema alone says nothing about content, and constrained decoding makes schema validity
nearly free, so items can also pin key values (by JSON Pointer) that the reply must contain.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import JsonValue

from llm_evals.scoring import Score
from llm_evals.scoring.matching import mismatch, resolve_pointer
from llm_evals.scoring.validation import schema_errors

# A reply that is one fenced block and nothing else. Clients strip this routinely, so it is
# not held against the model; JSON buried in prose is.
_FENCED = re.compile(r"^```[a-zA-Z]*\s*\n(?P<body>.*?)\n?```$", re.DOTALL)


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON")


def parse_json(text: str) -> JsonValue:
    """Parse a reply as strict JSON, unwrapping a single Markdown code fence.

    Raises ``ValueError``; Python's lenient ``NaN``/``Infinity`` literals are rejected too.
    """
    text = text.strip()
    if fenced := _FENCED.match(text):
        text = fenced["body"].strip()
    value: JsonValue = json.loads(text, parse_constant=_reject_constant)
    return value


def score_json(
    text: str, schema: dict[str, Any], expected: Mapping[str, JsonValue] | None = None
) -> Score:
    expected = expected or {}
    checks = {"valid_json": False, "schema_valid": False}
    if expected:
        checks["values_correct"] = False

    try:
        document = parse_json(text)
    except ValueError as exc:
        return Score(passed=False, reason=f"not valid JSON: {exc}", checks=checks)
    checks["valid_json"] = True

    if errors := schema_errors(document, schema):
        more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
        return Score(
            passed=False,
            extracted=document,
            reason=f"schema violation at {errors[0]}{more}",
            checks=checks,
        )
    checks["schema_valid"] = True

    for pointer, value in expected.items():
        try:
            actual = resolve_pointer(document, pointer)
        except LookupError:
            return Score(
                passed=False, extracted=document, reason=f"{pointer}: missing", checks=checks
            )
        if problem := mismatch(value, actual, pointer):
            return Score(passed=False, extracted=document, reason=problem, checks=checks)
    if expected:
        checks["values_correct"] = True
    return Score(passed=True, extracted=document, checks=checks)
