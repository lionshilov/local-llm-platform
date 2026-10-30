"""Tasks: how to prompt for a suite's items and how to score the replies.

A suite is data; a task is one way of running it. Most suites have exactly one task. The
JSON suite has two that send identical prompts and differ only in decoding: free-form
(``json/prompted``) and grammar-constrained via ``response_format`` (``json/constrained``).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

from llm_evals.client import ChatRequest
from llm_evals.reply import Reply
from llm_evals.scoring import Score
from llm_evals.scoring.choice import letters, score_choice
from llm_evals.scoring.instructions import render_prompt, score_instructions
from llm_evals.scoring.numeric import score_number
from llm_evals.scoring.structured import score_json
from llm_evals.scoring.tools import score_tool_calls
from llm_evals.suite import (
    ChoiceItem,
    ChoiceSuite,
    InstructionItem,
    InstructionsSuite,
    Item,
    JsonItem,
    JsonSuite,
    MathItem,
    MathSuite,
    Suite,
    SuiteBase,
    ToolItem,
    ToolsSuite,
)

ANSWER_NUMBER = (
    "Solve the problem step by step. Then give the final answer on its own last line "
    "in the form `Answer: <number>`, without units."
)
ANSWER_LETTER = (
    "Think it through, then give the final answer on its own last line "
    "in the form `Answer: <letter>`."
)
ANSWER_JSON = "Respond with only a JSON object that conforms to this JSON Schema:"


class Task[ItemT: Item](ABC):
    scoring: ClassVar[str]

    def __init__(self, suite: SuiteBase, items: Sequence[ItemT], variant: str = "") -> None:
        self.suite = suite.name
        self.name = f"{suite.name}/{variant}" if variant else suite.name
        self.items = items
        self._system = suite.system

    def messages(self, user: str) -> list[dict[str, Any]]:
        system = [{"role": "system", "content": self._system}] if self._system else []
        return [*system, {"role": "user", "content": user}]

    @abstractmethod
    def request(self, item: ItemT) -> ChatRequest: ...

    @abstractmethod
    def score(self, item: ItemT, reply: Reply) -> Score: ...


class MathTask(Task[MathItem]):
    scoring = "final number (Answer: line, else \\boxed{}, else last number) within tolerance"

    def request(self, item: MathItem) -> ChatRequest:
        return ChatRequest(self.messages(f"{item.question}\n\n{ANSWER_NUMBER}"))

    def score(self, item: MathItem, reply: Reply) -> Score:
        return score_number(reply.content, item.answer, item.tolerance)


class ChoiceTask(Task[ChoiceItem]):
    scoring = "answer letter (Answer: X, option X, or a bare letter)"

    def request(self, item: ChoiceItem) -> ChatRequest:
        options = "\n".join(
            f"{letter}) {option}"
            for letter, option in zip(letters(len(item.options)), item.options, strict=True)
        )
        return ChatRequest(self.messages(f"{item.question}\n\n{options}\n\n{ANSWER_LETTER}"))

    def score(self, item: ChoiceItem, reply: Reply) -> Score:
        return score_choice(reply.content, item.answer, len(item.options))


class JsonTask(Task[JsonItem]):
    scoring = "parses as JSON, validates against the schema, key values match"

    def __init__(self, suite: JsonSuite, *, constrained: bool) -> None:
        super().__init__(suite, suite.items, "constrained" if constrained else "prompted")
        self.constrained = constrained

    def request(self, item: JsonItem) -> ChatRequest:
        schema = json.dumps(item.json_schema, indent=2)
        messages = self.messages(f"{item.task}\n\n{ANSWER_JSON}\n{schema}")
        if not self.constrained:
            return ChatRequest(messages)
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": item.json_schema},
        }
        return ChatRequest(messages, response_format=response_format)

    def score(self, item: JsonItem, reply: Reply) -> Score:
        return score_json(reply.content, item.json_schema, item.expected)


class ToolsTask(Task[ToolItem]):
    scoring = "exact set of calls; arguments schema-valid and equal after normalization"

    def __init__(self, suite: ToolsSuite) -> None:
        super().__init__(suite, suite.items)
        self.tools = {tool.name: tool for tool in suite.tools}
        self._definitions = [tool.to_openai() for tool in suite.tools]

    def request(self, item: ToolItem) -> ChatRequest:
        return ChatRequest(self.messages(item.prompt), tools=self._definitions)

    def score(self, item: ToolItem, reply: Reply) -> Score:
        return score_tool_calls(item.calls, reply.tool_calls, self.tools)


class InstructionsTask(Task[InstructionItem]):
    scoring = "every instruction verified in code (prompt-level strict)"

    def request(self, item: InstructionItem) -> ChatRequest:
        return ChatRequest(self.messages(render_prompt(item.task, item.instructions)))

    def score(self, item: InstructionItem, reply: Reply) -> Score:
        return score_instructions(reply.content, item.instructions)


def tasks_for(suite: Suite) -> list[Task[Any]]:
    match suite:
        case MathSuite():
            return [MathTask(suite, suite.items)]
        case ChoiceSuite():
            return [ChoiceTask(suite, suite.items)]
        case JsonSuite():
            return [JsonTask(suite, constrained=False), JsonTask(suite, constrained=True)]
        case ToolsSuite():
            return [ToolsTask(suite)]
        case InstructionsSuite():
            return [InstructionsTask(suite, suite.items)]
