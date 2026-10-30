"""Verifiable instructions: each one renders its own prompt sentence and checks it in code.

Generating the instruction text from the same object that verifies it means the prompt can
never ask for something the checker does not test. Checks are strict, like IFEval's
"strict" mode: no lowercasing, no stripping of Markdown, no partial credit within an
instruction.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_evals.scoring import Score

_WORD = re.compile(r"\w+(?:['\u2019-]\w+)*")
_BULLET = re.compile(r"^\s*[-*+•]\s+\S", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)
# Emphasis as CommonMark renders it: no whitespace just inside the asterisks.
_HIGHLIGHT = re.compile(r"\*[^\s*](?:[^\n*]*[^\s*])?\*")
_PLACEHOLDER = re.compile(r"\[[^\[\]\n]+\]")
_TITLE = re.compile(r"<<[^<>\n]+>>")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


def _straight_quotes(text: str) -> str:
    """Typographic quotes are not a reason to fail an exact-phrase check."""
    return text.translate(_QUOTES)


def _quote(text: str) -> str:
    return f'"{text}"'


class Instruction(BaseModel, ABC):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @abstractmethod
    def describe(self) -> str:
        """The sentence appended to the prompt."""

    @abstractmethod
    def verify(self, text: str) -> str | None:
        """Return ``None`` if ``text`` follows the instruction, otherwise what is wrong."""


class BulletPoints(Instruction):
    type: Literal["bullet_points"] = "bullet_points"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return (
            f"Your answer must contain exactly {self.n} bullet points. "
            'Use Markdown bullets such as "- point".'
        )

    def verify(self, text: str) -> str | None:
        found = len(_BULLET.findall(text))
        return None if found == self.n else f"{found} bullet points, expected {self.n}"


class NumberedList(Instruction):
    type: Literal["numbered_list"] = "numbered_list"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return f"Your answer must contain a numbered list with exactly {self.n} items (1. 2. ...)."

    def verify(self, text: str) -> str | None:
        found = len(_NUMBERED.findall(text))
        return None if found == self.n else f"{found} numbered items, expected {self.n}"


class Lowercase(Instruction):
    type: Literal["lowercase"] = "lowercase"

    def describe(self) -> str:
        return "Your entire response must be in lowercase letters; no capital letters are allowed."

    def verify(self, text: str) -> str | None:
        capitals = [c for c in text if c.isupper()]
        return None if not capitals else f"{len(capitals)} capital letter(s), e.g. {capitals[0]!r}"


class Uppercase(Instruction):
    type: Literal["uppercase"] = "uppercase"

    def describe(self) -> str:
        return "Your entire response must be in English, using capital letters only."

    def verify(self, text: str) -> str | None:
        lower = [c for c in text if c.islower()]
        return None if not lower else f"{len(lower)} lowercase letter(s), e.g. {lower[0]!r}"


class KeywordCount(Instruction):
    type: Literal["keyword_count"] = "keyword_count"
    keyword: str = Field(min_length=1)
    at_least: int = Field(gt=0)

    def describe(self) -> str:
        return f"Include the word {_quote(self.keyword)} at least {self.at_least} times."

    def verify(self, text: str) -> str | None:
        pattern = rf"\b{re.escape(self.keyword)}\b"
        found = len(re.findall(pattern, text, re.IGNORECASE))
        if found >= self.at_least:
            return None
        return f"{self.keyword!r} appears {found} time(s), expected at least {self.at_least}"


class ForbiddenWords(Instruction):
    type: Literal["forbidden_words"] = "forbidden_words"
    words: list[str] = Field(min_length=1)

    def describe(self) -> str:
        return f"Do not use these words: {', '.join(_quote(w) for w in self.words)}."

    def verify(self, text: str) -> str | None:
        used = [w for w in self.words if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE)]
        return None if not used else f"used forbidden word(s): {', '.join(used)}"


class MaxWords(Instruction):
    type: Literal["max_words"] = "max_words"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return f"Answer in at most {self.n} words."

    def verify(self, text: str) -> str | None:
        found = count_words(text)
        return None if found <= self.n else f"{found} words, limit {self.n}"


class MinWords(Instruction):
    type: Literal["min_words"] = "min_words"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return f"Answer in at least {self.n} words."

    def verify(self, text: str) -> str | None:
        found = count_words(text)
        return None if found >= self.n else f"{found} words, minimum {self.n}"


class StartsWith(Instruction):
    type: Literal["starts_with"] = "starts_with"
    phrase: str = Field(min_length=1)

    def describe(self) -> str:
        return f"Start your response with the exact phrase {_quote(self.phrase)}."

    def verify(self, text: str) -> str | None:
        start = _straight_quotes(text.lstrip())
        if start.startswith(_straight_quotes(self.phrase)):
            return None
        return f"starts with {start[: len(self.phrase) + 10]!r}"


class EndsWith(Instruction):
    type: Literal["ends_with"] = "ends_with"
    phrase: str = Field(min_length=1)

    def describe(self) -> str:
        return (
            f"End your response with the exact phrase {_quote(self.phrase)}. "
            "No other words should follow it."
        )

    def verify(self, text: str) -> str | None:
        end = _straight_quotes(text.rstrip())
        if end.endswith(_straight_quotes(self.phrase)):
            return None
        return f"ends with {end[-(len(self.phrase) + 10) :]!r}"


class NoCommas(Instruction):
    type: Literal["no_commas"] = "no_commas"

    def describe(self) -> str:
        return "Do not use any commas in your response."

    def verify(self, text: str) -> str | None:
        found = text.count(",") + text.count("\uff0c")  # ASCII + full-width
        return None if not found else f"{found} comma(s)"


class Paragraphs(Instruction):
    type: Literal["paragraphs"] = "paragraphs"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return f"Write exactly {self.n} paragraphs, separated from each other by a blank line."

    def verify(self, text: str) -> str | None:
        found = len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()])
        return None if found == self.n else f"{found} paragraphs, expected {self.n}"


class Title(Instruction):
    type: Literal["title"] = "title"

    def describe(self) -> str:
        return "Include a title wrapped in double angular brackets, such as <<my title>>."

    def verify(self, text: str) -> str | None:
        return None if _TITLE.search(text) else "no <<title>>"


class Postscript(Instruction):
    type: Literal["postscript"] = "postscript"
    marker: str = "P.S."

    def describe(self) -> str:
        return f"At the end of your response, add a postscript starting with {self.marker}"

    def verify(self, text: str) -> str | None:
        pattern = rf"^[\s*_]*{re.escape(self.marker)}"
        return None if re.search(pattern, text, re.MULTILINE) else f"no line starting {self.marker}"


class Quoted(Instruction):
    type: Literal["quoted"] = "quoted"

    def describe(self) -> str:
        return "Wrap your entire response in double quotation marks."

    def verify(self, text: str) -> str | None:
        body = text.strip()
        ok = len(body) >= 2 and body[0] in '"“' and body[-1] in '"”'
        return None if ok else "not wrapped in double quotes"


class Placeholders(Instruction):
    type: Literal["placeholders"] = "placeholders"
    at_least: int = Field(gt=0)

    def describe(self) -> str:
        return (
            f"Include at least {self.at_least} placeholders in square brackets, such as [address]."
        )

    def verify(self, text: str) -> str | None:
        found = len(_PLACEHOLDER.findall(text))
        if found >= self.at_least:
            return None
        return f"{found} placeholder(s), expected at least {self.at_least}"


class Sections(Instruction):
    type: Literal["sections"] = "sections"
    n: int = Field(gt=0)

    def describe(self) -> str:
        return (
            f"Divide your response into exactly {self.n} sections. Begin each section with "
            "SECTION X, where X is the section number."
        )

    def verify(self, text: str) -> str | None:
        found = len(re.findall(r"^[\W_]*SECTION\s+\d+", text, re.MULTILINE))
        return None if found == self.n else f"{found} sections, expected {self.n}"


class Highlights(Instruction):
    type: Literal["highlights"] = "highlights"
    at_least: int = Field(gt=0)

    def describe(self) -> str:
        return (
            f"Highlight at least {self.at_least} parts of your answer with Markdown, "
            "e.g. *highlighted part*."
        )

    def verify(self, text: str) -> str | None:
        found = len(_HIGHLIGHT.findall(text))
        if found >= self.at_least:
            return None
        return f"{found} highlighted part(s), expected at least {self.at_least}"


class MarkdownTable(Instruction):
    type: Literal["markdown_table"] = "markdown_table"
    rows: int = Field(gt=0, description="Data rows, not counting the header.")
    columns: int = Field(gt=0)

    def describe(self) -> str:
        return (
            f"Present the answer as a Markdown table with exactly {self.columns} columns and "
            f"{self.rows} data rows, plus a header row."
        )

    def verify(self, text: str) -> str | None:
        tables = _tables(text)
        if len(tables) != 1:
            return f"{len(tables)} Markdown tables, expected 1"
        header, *body = tables[0]
        if len(header) != self.columns:
            return f"{len(header)} columns, expected {self.columns}"
        if any(len(row) != len(header) for row in body):
            return "rows have different numbers of cells"
        return None if len(body) == self.rows else f"{len(body)} data rows, expected {self.rows}"


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _tables(text: str) -> list[list[list[str]]]:
    """Every GFM table in ``text``: header row first, then data rows (separator dropped)."""
    tables: list[list[list[str]]] = []
    block: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.strip().startswith("|"):
            block.append(line.strip())
            continue
        if len(block) >= 2 and _TABLE_SEPARATOR.match(block[1]):
            tables.append([_cells(row) for row in (block[0], *block[2:])])
        block = []
    return tables


AnyInstruction = Annotated[
    BulletPoints
    | NumberedList
    | Lowercase
    | Uppercase
    | KeywordCount
    | ForbiddenWords
    | MaxWords
    | MinWords
    | StartsWith
    | EndsWith
    | NoCommas
    | Paragraphs
    | Title
    | Postscript
    | Quoted
    | Placeholders
    | Sections
    | Highlights
    | MarkdownTable,
    Field(discriminator="type"),
]


def render_prompt(task: str, instructions: list[AnyInstruction]) -> str:
    return " ".join([task, *(instruction.describe() for instruction in instructions)])


def score_instructions(text: str, instructions: list[AnyInstruction]) -> Score:
    """Pass only if every instruction is followed (IFEval's prompt-level strict accuracy).

    Per-instruction results go into ``checks``, giving instruction-level accuracy too.
    """
    checks: dict[str, bool] = {}
    problems: list[str] = []
    for instruction in instructions:
        problem = instruction.verify(text)
        checks[instruction.type] = problem is None
        if problem:
            problems.append(f"{instruction.type}: {problem}")
    return Score(passed=not problems, reason="; ".join(problems) or None, checks=checks)
