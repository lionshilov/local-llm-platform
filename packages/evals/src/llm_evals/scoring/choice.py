"""Extract a multiple-choice answer letter.

Only explicit signals count: an ``Answer: X`` marker, "option X" / "choice X", or a reply
that is nothing but the letter. Guessing from any capital letter would misread "I" and "A"
in ordinary prose.
"""

from __future__ import annotations

import re

from llm_evals.scoring import Score

_MARKER = re.compile(
    r"(?i:\banswer\b)[*_\s]*(?i:is\b)?[*_\s]*[:\uff1a]?[*_\s(\[]*(?P<letter>[A-Z])(?![A-Za-z])"
)
_OPTION = re.compile(r"(?i:\b(?:option|choice)\b)\s*\(?(?P<letter>[A-Z])(?![A-Za-z])")
_BARE = re.compile(r"^\W*(?P<letter>[A-Z])\W*$")


def letters(n_options: int) -> str:
    return "ABCDEFGHIJ"[:n_options]


def extract_choice(text: str, valid: str) -> tuple[str, bool] | None:
    """Return the chosen letter and whether it came from an ``Answer:`` marker."""
    for pattern, explicit in ((_MARKER, True), (_OPTION, False), (_BARE, False)):
        found = [m["letter"] for m in pattern.finditer(text.strip()) if m["letter"] in valid]
        if found:
            return found[-1], explicit
    return None


def score_choice(text: str, answer: str, n_options: int) -> Score:
    extracted = extract_choice(text, letters(n_options))
    if extracted is None:
        return Score(passed=False, reason="no answer letter in the reply", checks={"format": False})
    letter, explicit = extracted
    checks = {"format": explicit}
    if letter == answer:
        return Score(passed=True, extracted=letter, checks=checks)
    return Score(
        passed=False, extracted=letter, reason=f"expected {answer}, got {letter}", checks=checks
    )
