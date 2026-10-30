"""Suite files: typed models for every kind of item, and loading from package data.

Suites live in ``llm_evals/suites/*.yaml`` and are validated on load, so a malformed item
fails immediately instead of silently scoring as wrong halfway through a run.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from functools import cache
from importlib.resources import files
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from llm_evals.scoring.choice import letters
from llm_evals.scoring.instructions import AnyInstruction
from llm_evals.scoring.tools import ExpectedCall, ToolSpec
from llm_evals.scoring.validation import check_schema


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)


class MathItem(Item):
    question: str
    answer: float
    tolerance: float = Field(default=1e-6, ge=0, description="Absolute tolerance.")


class ChoiceItem(Item):
    question: str
    options: list[str] = Field(min_length=2, max_length=10)
    answer: str = Field(pattern=r"^[A-J]$")

    @model_validator(mode="after")
    def _answer_is_an_option(self) -> ChoiceItem:
        if self.answer not in letters(len(self.options)):
            raise ValueError(f"answer {self.answer} is not one of the {len(self.options)} options")
        return self


class JsonItem(Item):
    task: str
    json_schema: dict[str, Any]
    expected: dict[str, JsonValue] = Field(
        default_factory=dict, description="JSON Pointer -> expected value (or matcher)."
    )
    reference: JsonValue = Field(description="A correct answer; the test suite scores it.")

    @model_validator(mode="after")
    def _schema_is_valid(self) -> JsonItem:
        check_schema(self.json_schema)
        return self


class ToolItem(Item):
    prompt: str
    calls: list[ExpectedCall] = Field(description="Expected calls; empty means do not call.")


class InstructionItem(Item):
    task: str
    instructions: list[AnyInstruction] = Field(min_length=1)
    reference: str | None = Field(default=None, description="A response that passes.")

    @model_validator(mode="after")
    def _one_instruction_per_type(self) -> InstructionItem:
        kinds = [instruction.type for instruction in self.instructions]
        if len(kinds) != len(set(kinds)):
            raise ValueError(f"{self.id}: an instruction type appears twice")
        return self


class SuiteBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    system: str | None = Field(default=None, description="System prompt for every item.")
    items: Sequence[Item]

    @model_validator(mode="after")
    def _unique_ids(self) -> SuiteBase:
        ids = [item.id for item in self.items]
        if duplicates := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"duplicate item ids: {', '.join(duplicates)}")
        return self

    @property
    def fingerprint(self) -> str:
        """Content hash, so result files record exactly which version of a suite was run."""
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]


class MathSuite(SuiteBase):
    kind: Literal["math"]
    items: list[MathItem]


class ChoiceSuite(SuiteBase):
    kind: Literal["choice"]
    items: list[ChoiceItem]


class JsonSuite(SuiteBase):
    kind: Literal["json"]
    items: list[JsonItem]


class ToolsSuite(SuiteBase):
    kind: Literal["tools"]
    tools: list[ToolSpec] = Field(min_length=1)
    items: list[ToolItem]

    @model_validator(mode="after")
    def _calls_use_known_tools(self) -> ToolsSuite:
        known = {tool.name for tool in self.tools}
        for item in self.items:
            if unknown := {call.name for call in item.calls} - known:
                raise ValueError(f"{item.id}: unknown tool(s) {', '.join(sorted(unknown))}")
        for tool in self.tools:
            check_schema(tool.parameters)
        return self


class InstructionsSuite(SuiteBase):
    kind: Literal["instructions"]
    items: list[InstructionItem]


Suite = Annotated[
    MathSuite | ChoiceSuite | JsonSuite | ToolsSuite | InstructionsSuite,
    Field(discriminator="kind"),
]
_SUITE: TypeAdapter[Suite] = TypeAdapter(Suite)

# Display order: reasoning-heavy first, then format-heavy.
SUITE_NAMES = ("math", "reasoning", "json", "tools", "instructions")


def parse_suite(text: str) -> Suite:
    return _SUITE.validate_python(yaml.safe_load(text))


@cache
def load_suite(name: str) -> Suite:
    if name not in SUITE_NAMES:
        raise KeyError(f"unknown suite {name!r}; available: {', '.join(SUITE_NAMES)}")
    resource = files("llm_evals") / "suites" / f"{name}.yaml"
    suite = parse_suite(resource.read_text(encoding="utf-8"))
    if suite.name != name:
        raise ValueError(f"{name}.yaml declares name {suite.name!r}")
    return suite


def load_suites(names: Sequence[str] | None = None) -> dict[str, Suite]:
    return {name: load_suite(name) for name in names or SUITE_NAMES}
