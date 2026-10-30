from __future__ import annotations

import pytest
from llm_evals.scoring.numeric import extract_number, score_number


@pytest.mark.parametrize(
    ("text", "value", "source"),
    [
        ("Answer: 42", 42, "answer_line"),
        ("**Answer:** $1,234.50", 1234.5, "answer_line"),
        ("**Answer**: 7 apples", 7, "answer_line"),
        ("The answer is 19.", 19, "answer_line"),
        ("Final answer: -3", -3, "answer_line"),
        ("Answer: \u22123", -3, "answer_line"),  # Unicode minus sign
        ("Answer: 3/4", 0.75, "answer_line"),
        ("Answer: 2 1/2 cups", 2.5, "answer_line"),
        ("Answer: 25%", 25, "answer_line"),
        ("Answer: .5", 0.5, "answer_line"),
        ("Answer: 6 \u00d7 7 = 42", 42, "answer_line"),
        ("Answer: 15 minutes (= 900 seconds)", 15, "answer_line"),
        ("Answer: x = 5", 5, "answer_line"),
        ("Answer: \\boxed{\\frac{3}{4}}", 0.75, "answer_line"),
        ("We get 12 then 30.\n\\boxed{30}\nDone in 2 steps.", 30, "boxed"),
        ("It costs $8 per item, so the total is $56.", 56, "last_number"),
        ("Profit = 280,000 - 210,000 = 70,000", 70000, "last_number"),
    ],
)
def test_extracts_the_final_number(text: str, value: float, source: str) -> None:
    answer = extract_number(text)
    assert answer is not None
    assert answer.value == pytest.approx(value)
    assert answer.source == source


def test_last_answer_line_with_a_number_wins() -> None:
    text = "To answer this, 2 + 2 = 4.\nAnswer: 12\n\nI hope this answer helps!"
    answer = extract_number(text)
    assert answer is not None
    assert (answer.value, answer.source) == (12, "answer_line")


@pytest.mark.parametrize(
    "text",
    [
        "COVID-19 cases",  # the hyphen is not a minus sign
        "version 3.12.",  # a trailing period is not a decimal point
    ],
)
def test_signs_and_trailing_dots_are_not_misread(text: str) -> None:
    answer = extract_number(text)
    assert answer is not None
    assert answer.value > 0


def test_lists_are_not_thousands_separators() -> None:
    answer = extract_number("The values are 1,2,3")
    assert answer is not None
    assert answer.value == 3


@pytest.mark.parametrize("text", ["", "I don't know.", "Answer: none", "Answer: 1/0"])
def test_no_number(text: str) -> None:
    assert extract_number(text) is None


def test_score_uses_absolute_tolerance() -> None:
    assert score_number("Answer: 33.04", 33.04, tolerance=1e-6).passed
    assert not score_number("Answer: 33.0", 33.04, tolerance=1e-6).passed
    assert score_number("Answer: 33.0", 33.04, tolerance=0.05).passed


def test_score_records_format_and_reason() -> None:
    right = score_number("so it is 64", 64, tolerance=1e-6)
    assert right.passed
    assert right.checks == {"format": False}

    wrong = score_number("Answer: 280", 64, tolerance=1e-6)
    assert not wrong.passed
    assert wrong.extracted == 280
    assert wrong.reason == "expected 64, got 280 (from answer_line)"

    empty = score_number("", 64, tolerance=1e-6)
    assert empty.reason == "no number in the reply"
