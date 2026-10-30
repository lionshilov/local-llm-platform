from __future__ import annotations

import pytest
from llm_evals.scoring.matching import example_of, mismatch, resolve_pointer
from pydantic import JsonValue


@pytest.mark.parametrize(
    ("expected", "actual"),
    [
        ("New York", "  new   york "),
        (5, 5.0),
        (0.1 + 0.2, 0.3),
        (True, True),
        (None, None),
        (["Tom", "Priya"], ["priya", "TOM"]),
        ({"a": 1}, {"a": 1, "extra": "allowed"}),
        ({"$any_of": ["GOOGL", "GOOG"]}, "goog"),
        ({"$contains": "eiffel tower"}, "The Eiffel Tower, Paris"),
        ({"$length": 2}, ["x", "y"]),
        ([{"name": "frog", "class": "amphibian"}], [{"class": "amphibian", "name": "Frog"}]),
    ],
)
def test_matches(expected: JsonValue, actual: JsonValue) -> None:
    assert mismatch(expected, actual) is None


@pytest.mark.parametrize(
    ("expected", "actual", "problem"),
    [
        ("Lisbon", "Porto", "/: expected 'Lisbon', got 'Porto'"),
        (1, True, "/: expected 1, got True"),  # booleans are not numbers
        (True, 1, "/: expected True, got 1"),
        (5, "5", "/: expected 5, got '5'"),
        (["a", "b"], ["a"], "/: expected 2 element(s), got 1"),
        (["a", "a"], ["a", "b"], "/: expected ['a', 'a'] in any order, got ['a', 'b']"),
        ({"city": "Rome"}, {}, "/city: missing"),
        ({"city": {"$contains": "Rome"}}, {"city": "Milan"}, "/city: expected text containing"),
        ({"$length": 3}, "abc", "/: expected 3 element(s), got 'abc'"),
    ],
)
def test_mismatches(expected: JsonValue, actual: JsonValue, problem: str) -> None:
    found = mismatch(expected, actual)
    assert found is not None
    assert found.startswith(problem)


def test_malformed_matcher_is_an_authoring_error() -> None:
    with pytest.raises(ValueError, match="malformed matcher"):
        mismatch({"$any_of": "not a list"}, "x")


def test_resolve_pointer() -> None:
    document: JsonValue = {"items": [{"price": 9.99}], "a/b": {"~": 1}}
    assert resolve_pointer(document, "/items/0/price") == 9.99
    assert resolve_pointer(document, "/a~1b/~0") == 1
    assert resolve_pointer(document, "") == document
    for missing in ("/items/1", "/nope", "/items/x"):
        with pytest.raises(LookupError):
            resolve_pointer(document, missing)


def test_example_of_satisfies_its_own_matcher() -> None:
    expected: JsonValue = {
        "city": {"$contains": "Rome"},
        "ticker": {"$any_of": ["GOOGL", "GOOG"]},
        "tags": ["a", "b"],
    }
    assert mismatch(expected, example_of(expected)) is None
