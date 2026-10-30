"""Extract the final numeric answer from free-form model output.

Order of precedence, from most to least explicit:

1. the last ``Answer: ...`` (or "the answer is ...") line that contains a number,
2. the last LaTeX ``\\boxed{...}``,
3. the last number anywhere in the text.

Numbers may carry a sign, ``$``, thousands separators, decimals, or be simple and mixed
fractions (``3/4``, ``2 1/2``).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from llm_evals.scoring import Score

_NUMBER = re.compile(
    r"""
    (?<![\w.])                                   # not glued to a word or another number
    (?P<sign>[-\u2212])?\$?
    (?:
        (?P<whole>\d+)\ (?P<mixed_num>\d+)/(?P<mixed_den>\d+)   # mixed number: 2 1/2
      | (?P<num>\d+)\s*/\s*(?P<den>\d+)                          # fraction: 3/4
      | (?P<decimal>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)
    )
    """,
    re.VERBOSE,
)
_ANSWER_LINE = re.compile(r"(?i)\banswer\b[*_\s]*(?:is\b)?[*_\s]*[:\uff1a=]?(?P<rest>[^\n]*)")
_BOXED = re.compile(r"\\boxed\{(?P<inner>[^{}]*)\}")
_LATEX_FRACTION = re.compile(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}")
_ARITHMETIC = re.compile(r"\d\s*[-+*/x\u00d7\u00f7\u00b7]\s*\d")

Source = Literal["answer_line", "boxed", "last_number"]


@dataclass(frozen=True)
class NumericAnswer:
    value: float
    text: str
    source: Source


def _parse(match: re.Match[str]) -> float | None:
    sign = -1.0 if match["sign"] else 1.0
    if match["whole"] is not None:
        den = int(match["mixed_den"])
        return sign * (int(match["whole"]) + int(match["mixed_num"]) / den) if den else None
    if match["num"] is not None:
        den = int(match["den"])
        return sign * int(match["num"]) / den if den else None
    return sign * float(match["decimal"].replace(",", ""))


def _numbers(text: str) -> list[tuple[float, str]]:
    found = []
    for match in _NUMBER.finditer(text):
        value = _parse(match)
        if value is not None:
            found.append((value, match.group().strip()))
    return found


def _normalize_latex(text: str) -> str:
    text = _LATEX_FRACTION.sub(r"\1/\2", text)
    return text.replace("\\$", "$").replace("{,}", ",").replace("\\,", "").replace("\\!", "")


def _from_answer_segment(segment: str) -> tuple[float, str] | None:
    """First number after the marker; for ``6 * 7 = 42`` the result after the last ``=``."""
    head, sep, _ = segment.partition("=")
    if sep and _ARITHMETIC.search(head):
        segment = segment.rsplit("=", 1)[1]
    numbers = _numbers(segment)
    return numbers[0] if numbers else None


def extract_number(text: str) -> NumericAnswer | None:
    text = _normalize_latex(text)
    for match in reversed(list(_ANSWER_LINE.finditer(text))):
        found = _from_answer_segment(match["rest"])
        if found is not None:
            return NumericAnswer(found[0], found[1], "answer_line")
    boxed = _BOXED.findall(text)
    if boxed and (numbers := _numbers(boxed[-1])):
        return NumericAnswer(numbers[0][0], numbers[0][1], "boxed")
    if numbers := _numbers(text):
        return NumericAnswer(numbers[-1][0], numbers[-1][1], "last_number")
    return None


def score_number(text: str, expected: float, tolerance: float) -> Score:
    answer = extract_number(text)
    if answer is None:
        return Score(passed=False, reason="no number in the reply", checks={"format": False})
    checks = {"format": answer.source == "answer_line"}
    if math.isclose(answer.value, expected, rel_tol=1e-9, abs_tol=tolerance):
        return Score(passed=True, extracted=answer.value, checks=checks)
    return Score(
        passed=False,
        extracted=answer.value,
        reason=f"expected {expected:g}, got {answer.text} (from {answer.source})",
        checks=checks,
    )
