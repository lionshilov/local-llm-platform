from __future__ import annotations

import pytest
from llm_evals.scoring.choice import extract_choice, score_choice


@pytest.mark.parametrize(
    ("text", "letter", "explicit"),
    [
        ("Reasoning...\nAnswer: C", "C", True),
        ("**Answer:** **B**", "B", True),
        ("The answer is (D).", "D", True),
        ("Answer: A) Ada", "A", True),
        ("Answer: B\n\nOn reflection...\nAnswer: C", "C", True),
        ("I would pick option B.", "B", False),
        ("C", "C", False),
        ("**(A)**", "A", False),
    ],
)
def test_extracts_explicit_choices(text: str, letter: str, explicit: bool) -> None:
    assert extract_choice(text, "ABCD") == (letter, explicit)


@pytest.mark.parametrize(
    "text",
    [
        "I think A is a tricky one.",  # articles and pronouns are not answers
        "Answer: Bo",  # a name starting with a valid letter
        "Answer: E",  # not one of the offered options
        "",
    ],
)
def test_ignores_ambiguous_letters(text: str) -> None:
    assert extract_choice(text, "ABCD") is None


def test_score_choice() -> None:
    assert score_choice("Answer: B", "B", n_options=4).passed
    wrong = score_choice("Answer: A", "B", n_options=4)
    assert (wrong.passed, wrong.reason, wrong.extracted) == (False, "expected B, got A", "A")
    missing = score_choice("No idea.", "B", n_options=4)
    assert missing.checks == {"format": False}
