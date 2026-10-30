"""Turn typed Python functions into tools: a JSON schema for the model, validation for us.

The schema comes from the signature (types, defaults) and the docstring (summary and
``Args:`` descriptions), so a tool is written once, as an ordinary function::

    @tool
    def calculator(expression: str) -> str:
        \"\"\"Evaluate an arithmetic expression.

        Args:
            expression: For example ``(2 + 3) * sqrt(16)``.
        \"\"\"
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import typing
from collections.abc import Callable
from typing import Any, overload

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from llm_agent.tools.docstrings import parse_docstring

_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # what OpenAI-compatible APIs accept
# Schema keys whose values map *names* to sub-schemas, so their keys must survive title stripping.
_NAMED_SCHEMAS = frozenset({"properties", "$defs", "patternProperties"})
_LITERAL_VALUES = frozenset({"default", "const", "enum", "examples"})


class ToolError(Exception):
    """An expected tool failure; its message is shown to the model as is."""


class InvalidArgumentsError(ValueError):
    """The model's arguments are not valid JSON or do not match the tool's schema."""


def _strip_titles(node: Any) -> Any:
    """Drop pydantic's auto-generated titles: noise that costs small models context."""
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    if not isinstance(node, dict):
        return node
    stripped: dict[str, Any] = {}
    for key, value in node.items():
        if key == "title":
            continue
        if key in _NAMED_SCHEMAS and isinstance(value, dict):
            stripped[key] = {name: _strip_titles(sub) for name, sub in value.items()}
        elif key in _LITERAL_VALUES:
            stripped[key] = value
        else:
            stripped[key] = _strip_titles(value)
    return stripped


def _arguments_model(
    fn: Callable[..., Any], tool_name: str, descriptions: dict[str, str]
) -> type[BaseModel]:
    try:
        hints = typing.get_type_hints(fn, include_extras=True)
    except NameError as exc:
        raise TypeError(
            f"tool '{tool_name}': cannot resolve a type annotation ({exc}); "
            "types used by tools must be importable at module level"
        ) from exc
    fields: dict[str, Any] = {}
    for param in inspect.signature(fn).parameters.values():
        if param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
            raise TypeError(
                f"tool '{tool_name}': parameter '{param.name}' must be passable by keyword"
            )
        if param.name not in hints:
            raise TypeError(f"tool '{tool_name}': parameter '{param.name}' needs a type annotation")
        default = ... if param.default is param.empty else param.default
        description = descriptions.get(param.name)
        field = Field(default, description=description) if description else Field(default)
        fields[param.name] = (hints[param.name], field)
    config = ConfigDict(extra="forbid", protected_namespaces=())
    return create_model(f"{tool_name}_arguments", __config__=config, **fields)


def _validation_problems(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['msg']}"
        for error in exc.errors(include_url=False)
    )


class Tool[**P, R]:
    """A Python function the model can call. Calling the tool calls the function."""

    def __init__(
        self, fn: Callable[P, R], *, name: str | None = None, description: str | None = None
    ) -> None:
        self.fn = fn
        self.name = name or str(getattr(fn, "__name__", ""))  # partials have no __name__
        if not _NAME.match(self.name):
            raise ValueError(f"invalid tool name '{self.name}': use 1-64 of [A-Za-z0-9_-]")
        doc = parse_docstring(fn.__doc__)
        self.description = description or doc.summary
        if not self.description:
            raise ValueError(f"tool '{self.name}' needs a docstring or a description")
        self.arguments = _arguments_model(fn, self.name, doc.args)
        self.parameters: dict[str, Any] = _strip_titles(self.arguments.model_json_schema())
        self.is_async = inspect.iscoroutinefunction(fn)
        self._call: Callable[..., Any] = fn

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self.fn(*args, **kwargs)

    def __repr__(self) -> str:
        return f"Tool(name={self.name!r})"

    def schema(self) -> dict[str, Any]:
        """The tool definition as sent in the request's ``tools`` array."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def parse_arguments(self, raw: str) -> BaseModel:
        """Validate the model's JSON arguments; errors explain how to fix the call."""
        expected = json.dumps(self.parameters, separators=(",", ":"))
        try:
            data = json.loads(raw.strip() or "{}")
            if isinstance(data, str):  # some models JSON-encode the arguments twice
                data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise InvalidArgumentsError(
                f"arguments for '{self.name}' are not valid JSON ({exc.msg} at position "
                f"{exc.pos}). Send one JSON object matching this schema: {expected}"
            ) from exc
        if not isinstance(data, dict):
            raise InvalidArgumentsError(
                f"arguments for '{self.name}' must be a JSON object, got "
                f"{type(data).__name__}. Schema: {expected}"
            )
        try:
            return self.arguments.model_validate(data)
        except ValidationError as exc:
            raise InvalidArgumentsError(
                f"invalid arguments for '{self.name}': {_validation_problems(exc)}. "
                f"Schema: {expected}"
            ) from exc

    async def invoke(self, arguments: BaseModel) -> Any:
        """Run the function: coroutines on the event loop, plain functions in a thread."""
        kwargs = {name: getattr(arguments, name) for name in type(arguments).model_fields}
        if self.is_async:
            return await self._call(**kwargs)
        return await asyncio.to_thread(self._call, **kwargs)


type AnyTool = Tool[..., Any]


@overload
def tool[**P, R](fn: Callable[P, R], /) -> Tool[P, R]: ...
@overload
def tool[**P, R](
    *, name: str | None = None, description: str | None = None
) -> Callable[[Callable[P, R]], Tool[P, R]]: ...
def tool[**P, R](
    fn: Callable[P, R] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Tool[P, R] | Callable[[Callable[P, R]], Tool[P, R]]:
    """Decorator: ``@tool`` or ``@tool(name=..., description=...)``."""

    def wrap(function: Callable[P, R]) -> Tool[P, R]:
        return Tool(function, name=name, description=description)

    return wrap if fn is None else wrap(fn)
