from __future__ import annotations

import math
import time

import pytest
from llm_agent.tools.calculator import CalculatorError, calculator, evaluate, format_number


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("7 / 2", 3.5),
        ("7 // 2", 3),
        ("-7 % 3", 2),
        ("2 ** 10", 1024),
        ("2 ** -1", 0.5),
        ("-(+3)", -3),
        ("sqrt(16) + abs(-2)", 6.0),
        ("log(e) + log(8, 2) + log10(1000)", 7.0),
        ("round(pi, 2)", 3.14),
        ("max(1, 5, 3) - min(4, 2)", 3),
        ("floor(2.7) + ceil(2.1)", 5),
    ],
)
def test_arithmetic(expression: str, expected: float) -> None:
    assert evaluate(expression) == pytest.approx(expected)


def test_trigonometry_uses_radians() -> None:
    assert evaluate("sin(pi / 2) + cos(0)") == pytest.approx(2.0)
    assert evaluate("atan(1) * 4") == pytest.approx(math.pi)


def test_tool_output_hides_float_noise() -> None:
    assert calculator(expression="0.1 + 0.2") == "0.3"
    assert calculator(expression="sqrt(16)") == "4"
    assert format_number(2**100) == str(2**100)


@pytest.mark.parametrize(
    ("expression", "error"),
    [
        ("__import__('os')", "unknown function '__import__'"),
        ("__import__('os').system('ls')", "only direct calls"),
        ("x + 1", "unknown name 'x'"),
        ("(1).__class__", "attribute access is not allowed"),
        ("math.sqrt(4)", "only direct calls"),
        ("open('/etc/passwd')", "unknown function 'open'"),
        ("[1, 2][0]", "unsupported syntax: Subscript"),
        ("1 if 2 else 3", "unsupported syntax: IfExp"),
        ("lambda: 1", "unsupported syntax: Lambda"),
        ("'a' * 3", "unsupported syntax: Constant"),
        ("True + 1", "booleans"),
        ("1 < 2", "unsupported syntax: Compare"),
        ("2 ^ 3", r"use \*\* for powers"),
        ("round(2.5, ndigits=1)", "positional arguments only"),
        ("1 / 0", "division by zero"),
        ("5 % 0", "division by zero"),
        ("sqrt(-1)", "math domain error"),
        ("(-8) ** (1/3)", "complex number"),
        ("1 +", "invalid expression"),
        ("1" * 600, "longer than 500 characters"),
    ],
)
def test_rejections(expression: str, error: str) -> None:
    with pytest.raises(CalculatorError, match=error):
        evaluate(expression)


@pytest.mark.parametrize(
    "expression",
    ["9 ** 9 ** 9", "2 ** 5000", "10 ** 1000 * 10 ** 1000 * 10 ** 1000", "exp(1000)", "1e308 * 10"],
)
def test_huge_numbers_fail_fast(expression: str) -> None:
    started = time.perf_counter()
    with pytest.raises(CalculatorError, match=r"too large|overflow|finite"):
        evaluate(expression)
    assert time.perf_counter() - started < 0.5  # computing any of these would take ages


def test_large_but_bounded_integers_are_exact() -> None:
    assert evaluate("2 ** 4000") == 2**4000
    assert evaluate("0.5 ** 100000") == 0.0
