from __future__ import annotations

import typing

import pytest
from llm_evals.scoring.instructions import (
    AnyInstruction,
    BulletPoints,
    EndsWith,
    ForbiddenWords,
    Highlights,
    Instruction,
    KeywordCount,
    Lowercase,
    MarkdownTable,
    MaxWords,
    MinWords,
    NoCommas,
    NumberedList,
    Paragraphs,
    Placeholders,
    Postscript,
    Quoted,
    Sections,
    StartsWith,
    Title,
    Uppercase,
    count_words,
    render_prompt,
    score_instructions,
)
from pydantic import TypeAdapter

TABLE = """Here is the comparison:

| Language | Typing |
|:---|---:|
| Python | dynamic |
| Go | static |
"""

# (instruction, passing response, failing response, expected problem for the failing one)
CASES: list[tuple[Instruction, str, str, str]] = [
    (BulletPoints(n=2), "Intro:\n- one\n* two", "- one\n- two\n- three", "3 bullet points"),
    (BulletPoints(n=1), "  + nested ok", "**bold** is not a bullet", "0 bullet points"),
    (NumberedList(n=3), "1. a\n2) b\n3. c", "1. a\n2. b", "2 numbered items"),
    (Lowercase(), "all quiet here.", "all quiet Here.", "1 capital letter(s), e.g. 'H'"),
    (Uppercase(), "LOUD, CLEAR, 100%!", "LOUD but not all", "lowercase letter(s)"),
    (
        KeywordCount(keyword="grid", at_least=2),
        "The Grid is a grid.",
        "Grids are not a grid.",
        "'grid' appears 1 time(s)",
    ),
    (ForbiddenWords(words=["rain", "storm"]), "Drizzle and rainfall.", "Rain!", "rain"),
    (MaxWords(n=5), "It's a well-known fact.", "one two three four five six", "6 words"),
    (MinWords(n=3), "one two three", "one two", "2 words, minimum 3"),
    (StartsWith(phrase="Dear landlord"), "  Dear landlord,\nhi", "Hello landlord", "starts with"),
    (
        EndsWith(phrase="Let's ship it!"),
        "Ready? Let\u2019s ship it!\n",
        "Let's ship it! Now.",
        "ends",
    ),
    (NoCommas(), "No commas here.", "One, two", "1 comma(s)"),
    (NoCommas(), "Fine.", "Full-width\uff0ccomma", "1 comma(s)"),
    (Paragraphs(n=2), "First.\n\n  \nSecond.", "Just one\nparagraph.", "1 paragraphs"),
    (Title(), "<<A Title>>\nBody", "<A Title>", "no <<title>>"),
    (Postscript(), "Body.\n\n**P.S.** Bye", "Body. PS bye", "no line starting P.S."),
    (Quoted(), '  "All of it."\n', '"Half" of it.', "not wrapped in double quotes"),
    (Quoted(), "\u201cCurly is fine.\u201d", '"', "not wrapped in double quotes"),
    (Placeholders(at_least=2), "[name] at [address]", "[name] only", "1 placeholder(s)"),
    (Sections(n=2), "SECTION 1\na\n## SECTION 2\nb", "Section 1\na\nSECTION 2\nb", "1 sections"),
    (Highlights(at_least=2), "*one* and **two**", "*one* and * not *", "1 highlighted"),
    (MarkdownTable(rows=2, columns=2), TABLE, TABLE.replace("| Go | static |\n", ""), "1 data"),
]


@pytest.mark.parametrize(("instruction", "good", "bad", "problem"), CASES)
def test_checker(instruction: Instruction, good: str, bad: str, problem: str) -> None:
    assert instruction.verify(good) is None
    found = instruction.verify(bad)
    assert found is not None
    assert problem in found


def test_every_instruction_type_is_covered() -> None:
    union = typing.get_args(typing.get_args(AnyInstruction)[0])
    assert {type(instruction) for instruction, *_ in CASES} == set(union)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("| a | b |\n| 1 | 2 |", "0 Markdown tables"),  # no separator row
        (TABLE + "\n" + TABLE, "2 Markdown tables"),
        ("| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |", "3 columns"),
        ("| a | b |\n|---|---|\n| 1 | 2 | 3 |\n| 4 | 5 |", "different numbers of cells"),
    ],
)
def test_markdown_table_problems(text: str, problem: str) -> None:
    found = MarkdownTable(rows=2, columns=2).verify(text)
    assert found is not None
    assert problem in found


def test_count_words_handles_contractions_and_hyphens() -> None:
    assert count_words("It's a well-known, state-of-the-art fact.") == 5


def test_instructions_parse_from_yaml_shape() -> None:
    adapter: TypeAdapter[AnyInstruction] = TypeAdapter(AnyInstruction)
    parsed = adapter.validate_python({"type": "keyword_count", "keyword": "x", "at_least": 2})
    assert parsed == KeywordCount(keyword="x", at_least=2)


def test_prompt_is_rendered_from_the_checks() -> None:
    prompt = render_prompt("Describe rain.", [Lowercase(), MaxWords(n=20)])
    assert prompt == (
        "Describe rain. Your entire response must be in lowercase letters; "
        "no capital letters are allowed. Answer in at most 20 words."
    )


def test_score_is_prompt_level_strict_with_instruction_level_checks() -> None:
    instructions: list[AnyInstruction] = [Lowercase(), NoCommas(), MaxWords(n=3)]
    score = score_instructions("Hello, big world", instructions)
    assert not score.passed
    assert score.checks == {"lowercase": False, "no_commas": False, "max_words": True}
    assert score.reason == "lowercase: 1 capital letter(s), e.g. 'H'; no_commas: 1 comma(s)"
    assert score_instructions("hello big world", instructions).passed
