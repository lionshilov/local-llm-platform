"""Compare model-produced values with expected ones, tolerating irrelevant differences.

* strings: case-insensitive, surrounding and repeated whitespace ignored
* numbers: ``5 == 5.0``, relative tolerance 1e-6; booleans are never numbers
* lists: same length, order-insensitive
* objects: every expected key must match; extra keys are allowed (schemas police those)

Expected values can also be matchers, written as single-key objects:

* ``{"$any_of": [a, b]}``: matches if any alternative matches
* ``{"$contains": "text"}``: a string containing ``text`` (case-insensitive)
* ``{"$length": n}``: a list with exactly ``n`` elements
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeGuard

from pydantic import JsonValue

_MATCHERS = frozenset({"$any_of", "$contains", "$length"})


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _show(value: object) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def is_matcher(value: object) -> TypeGuard[dict[str, JsonValue]]:
    return isinstance(value, dict) and len(value) == 1 and next(iter(value)) in _MATCHERS


def mismatch(expected: JsonValue, actual: JsonValue, path: str = "") -> str | None:
    """Return ``None`` if ``actual`` matches ``expected``, otherwise where and how it differs."""
    if is_matcher(expected):
        return _match_operator(expected, actual, path)
    if isinstance(expected, list):
        return _match_list(expected, actual, path)
    if isinstance(expected, dict):
        return _match_object(expected, actual, path)
    if isinstance(expected, bool) or expected is None:
        ok = actual is expected
    elif isinstance(expected, str):
        ok = isinstance(actual, str) and _norm(actual) == _norm(expected)
    else:
        ok = _is_number(actual) and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9)
    return None if ok else f"{path or '/'}: expected {_show(expected)}, got {_show(actual)}"


def _match_operator(matcher: dict[str, JsonValue], actual: JsonValue, path: str) -> str | None:
    where = path or "/"
    [(operator, operand)] = matcher.items()
    match operator, operand:
        case "$any_of", list():
            if any(mismatch(option, actual, path) is None for option in operand):
                return None
            return f"{where}: expected one of {_show(operand)}, got {_show(actual)}"
        case "$contains", str():
            if isinstance(actual, str) and _norm(operand) in _norm(actual):
                return None
            return f"{where}: expected text containing {operand!r}, got {_show(actual)}"
        case "$length", int():
            if isinstance(actual, list) and len(actual) == operand:
                return None
            got = len(actual) if isinstance(actual, list) else _show(actual)
            return f"{where}: expected {operand} element(s), got {got}"
        case _:
            raise ValueError(f"malformed matcher {matcher!r}")


def _match_list(expected: list[JsonValue], actual: JsonValue, path: str) -> str | None:
    where = path or "/"
    if not isinstance(actual, list):
        return f"{where}: expected a list, got {_show(actual)}"
    if len(actual) != len(expected):
        return f"{where}: expected {len(expected)} element(s), got {len(actual)}"
    if _assign(expected, actual, path):
        return None
    return f"{where}: expected {_show(expected)} in any order, got {_show(actual)}"


def _assign(expected: Sequence[JsonValue], actual: Sequence[JsonValue], path: str) -> bool:
    """Backtracking search for a one-to-one pairing (lists here are a handful of items)."""
    if not expected:
        return True
    head, rest = expected[0], expected[1:]
    for i, candidate in enumerate(actual):
        if mismatch(head, candidate, path) is None and _assign(
            rest, [*actual[:i], *actual[i + 1 :]], path
        ):
            return True
    return False


def _match_object(expected: dict[str, JsonValue], actual: JsonValue, path: str) -> str | None:
    if not isinstance(actual, dict):
        return f"{path or '/'}: expected an object, got {_show(actual)}"
    for key, value in expected.items():
        child = f"{path}/{key}"
        if key not in actual:
            return f"{child}: missing"
        if problem := mismatch(value, actual[key], child):
            return problem
    return None


def resolve_pointer(document: JsonValue, pointer: str) -> JsonValue:
    """Resolve an RFC 6901 JSON Pointer such as ``/items/0/price``.

    Raises ``LookupError`` if the path does not exist.
    """
    node = document
    for raw in pointer.removeprefix("/").split("/") if pointer.strip("/") else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            raise LookupError(pointer)
    return node


def example_of(expected: JsonValue) -> JsonValue:
    """A concrete value that ``expected`` accepts; used to self-test the suite files."""
    if is_matcher(expected):
        [(operator, operand)] = expected.items()
        if operator == "$any_of" and isinstance(operand, list):
            return example_of(operand[0])
        if operator == "$contains":
            return operand
        raise ValueError(f"no example for {operator}")
    if isinstance(expected, list):
        return [example_of(value) for value in expected]
    if isinstance(expected, dict):
        return {key: example_of(value) for key, value in expected.items()}
    return expected
