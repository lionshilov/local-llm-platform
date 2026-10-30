from __future__ import annotations

from typing import Annotated, Any, Literal

import pytest
from llm_agent.tools import Tool, tool
from llm_agent.tools.docstrings import parse_docstring
from pydantic import BaseModel, Field


@tool
def search(
    query: str,
    limit: int = 5,
    sort: Literal["relevance", "date"] = "relevance",
    tags: list[str] | None = None,
) -> list[str]:
    """Search the notes.

    Matches titles and bodies.

    Args:
        query: Words to look for.
        limit: Maximum number of hits,
            between 1 and 50.
        sort (str): Result order.

    Returns:
        Matching note titles.
    """
    return [query] * limit


def test_schema_comes_from_signature_and_docstring() -> None:
    assert search.schema() == {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the notes.\n\nMatches titles and bodies.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Words to look for."},
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum number of hits, between 1 and 50.",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["relevance", "date"],
                        "default": "relevance",
                        "description": "Result order.",
                    },
                    "tags": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "default": None,
                    },
                },
            },
        },
    }


def test_decorated_tool_is_still_callable() -> None:
    assert search("x", limit=2) == ["x", "x"]
    assert not search.is_async


def test_annotated_field_metadata_and_overrides() -> None:
    @tool(name="add-numbers", description="Add two numbers.")
    async def add(a: Annotated[int, Field(ge=0, description="First addend.")], b: int) -> int:
        return a + b

    params = add.parameters
    assert add.name == "add-numbers"
    assert add.description == "Add two numbers."
    assert add.is_async
    assert params["properties"]["a"] == {
        "type": "integer",
        "minimum": 0,
        "description": "First addend.",
    }
    assert params["required"] == ["a", "b"]


class Section(BaseModel):
    title: str


def test_parameter_named_title_survives_title_stripping() -> None:
    @tool
    def publish(title: str, sections: list[Section]) -> str:
        """Publish a document."""
        return title

    params = publish.parameters
    assert set(params["properties"]) == {"title", "sections"}
    assert "title" not in params["properties"]["title"]
    assert params["$defs"]["Section"]["properties"] == {"title": {"type": "string"}}


def _no_docstring(x: int) -> int:
    return x


def _untyped(x):  # type: ignore[no-untyped-def]
    """Untyped."""
    return x


def _variadic(*values: int) -> int:
    """Variadic."""
    return sum(values)


def _local_type() -> Any:
    class Local(BaseModel):
        x: int

    def uses_local(item: Local) -> int:
        """Uses a type that only exists inside a function."""
        return item.x

    return uses_local


@pytest.mark.parametrize(
    ("fn", "kwargs", "error"),
    [
        (_no_docstring, {}, "needs a docstring"),
        (_untyped, {}, "needs a type annotation"),
        (_variadic, {}, "passable by keyword"),
        (_local_type(), {}, "must be importable at module level"),
        (_no_docstring, {"name": "bad name!", "description": "x"}, "invalid tool name"),
    ],
)
def test_invalid_tools_are_rejected(fn: Any, kwargs: dict[str, Any], error: str) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        Tool(fn, **kwargs)


def test_docstring_parser_handles_sections_and_continuations() -> None:
    doc = parse_docstring(
        """Summary line
        continues here.

        Arguments:
            path (str): Where to look.
            *rest: Ignored, but parsed.

        Raises:
            ValueError: never.
        """
    )
    assert doc.summary == "Summary line continues here."
    assert doc.args == {"path": "Where to look.", "rest": "Ignored, but parsed."}
    assert parse_docstring(None).summary == ""
